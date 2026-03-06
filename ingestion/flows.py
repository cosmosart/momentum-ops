"""
Prefect flows for market-data ingestion.

Converts the legacy ``APScheduler``-based ``DataScheduler`` into composable
Prefect tasks and flows.  Two top-level flows are defined:

* ``krx_realtime_flow``  — runs every 5 min during KRX trading hours.
* ``daily_batch_flow``   — runs once per day after US market close.

Each flow is self-contained and uses the shared connection pool (via
:pymod:`shared.database`) rather than a long-lived ``Database`` instance.

Deployments are configured in ``prefect.yaml`` at the repo root.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
from prefect import flow, get_run_logger, task
from prefect.tasks import task_input_hash

from ingestion.fetcher import DataFetcher
from models.features import engineer_features
from models.models import FourModelPredictor, calculate_indicators
from shared.config import settings, to_yf_symbol
from shared.database import get_connection

logger = logging.getLogger(__name__)

# Minimum daily rows before feature engineering is reliable.
MIN_HISTORY_ROWS: int = settings.min_history_rows


# ──────────────────────────────────────────────────────────────────────────────
# Tasks
# ──────────────────────────────────────────────────────────────────────────────


@task(
    name="fetch-active-tickers",
    retries=2,
    retry_delay_seconds=10,
    description="Query the tickers table for all rows with is_active = true.",
)
def fetch_active_tickers() -> list[dict[str, str]]:
    """Return a list of active ticker dicts ({'symbol', 'region'}) from the database."""
    log = get_run_logger()
    query = "SELECT symbol, market_region FROM tickers WHERE is_active = true ORDER BY symbol"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            tickers = [{"symbol": row["symbol"], "region": row["market_region"]} for row in cur.fetchall()]
    log.info("Active tickers: %d found", len(tickers))
    return tickers


@task(
    name="fetch-yfinance-daily",
    retries=3,
    retry_delay_seconds=30,
    cache_key_fn=task_input_hash,
    cache_expiration=pd.Timedelta(hours=1),
    description="Download daily OHLCV data for a single ticker via yfinance.",
)
def fetch_yfinance_daily(yf_symbol: str, period: str = "3mo") -> pd.DataFrame | None:
    """
    Fetch daily historical data from yfinance.

    Parameters
    ----------
    yf_symbol : str
        yfinance-compatible symbol (e.g. ``"AAPL"``, ``"069500.KS"``).
    period : str
        yfinance period string (``"3mo"``, ``"max"``, etc.).

    Returns
    -------
    pd.DataFrame | None
        DataFrame with OHLCV columns, or ``None`` on failure.
    """
    log = get_run_logger()
    fetcher = DataFetcher(yf_symbol)
    df = fetcher.fetch_daily_data(period=period)
    if df is None or df.empty:
        log.warning("No daily data returned for %s (period=%s)", yf_symbol, period)
        return None
    log.info("%s — fetched %d daily rows (%s → %s)", yf_symbol, len(df), df["Date"].iloc[0].date(), df["Date"].iloc[-1].date())
    return df


@task(
    name="fetch-yfinance-realtime",
    retries=2,
    retry_delay_seconds=15,
    description="Fetch latest 1-min bar from yfinance.",
)
def fetch_yfinance_realtime(yf_symbol: str) -> dict[str, Any] | None:
    """Fetch realtime (1-min) price snapshot for *yf_symbol*."""
    log = get_run_logger()
    fetcher = DataFetcher(yf_symbol)
    data = fetcher.fetch_realtime_data()
    if data is None:
        log.warning("No realtime data for %s", yf_symbol)
    return data


@task(
    name="upsert-daily-prices",
    retries=2,
    retry_delay_seconds=10,
    description="Batch-upsert daily OHLCV rows into price_daily.",
)
def upsert_daily_prices(ticker: str, region: str, df: pd.DataFrame) -> int:
    """
    Batch-upsert daily price rows in a single transaction.

    Returns the number of rows written.
    """
    log = get_run_logger()
    rows: list[tuple[str, str, date, float, float, float, float, float, int]] = [
        (
            ticker,
            region,
            r["Date"].date(),
            float(r["Open"]),
            float(r["High"]),
            float(r["Low"]),
            float(r["Close"]),
            float(r["Close"]),  # adj_close — yfinance already adjusts
            int(r["Volume"]),
        )
        for _, r in df.iterrows()
    ]
    query = """
        INSERT INTO price_daily
            (ticker, region, date, open, high, low, close, adj_close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, date) DO UPDATE SET
            region    = EXCLUDED.region,
            open      = EXCLUDED.open,
            high      = EXCLUDED.high,
            low       = EXCLUDED.low,
            close     = EXCLUDED.close,
            adj_close = EXCLUDED.adj_close,
            volume    = EXCLUDED.volume
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(query, rows)
        conn.commit()
    log.info("%s — upserted %d daily rows", ticker, len(rows))
    return len(rows)


@task(
    name="upsert-realtime-price",
    retries=2,
    retry_delay_seconds=10,
    description="Upsert a single realtime price snapshot into price_realtime.",
)
def upsert_realtime_price(data: dict[str, Any]) -> None:
    """Insert a single realtime price row."""
    query = """
        INSERT INTO price_realtime (ticker, region, timestamp, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, timestamp) DO UPDATE SET
            region = EXCLUDED.region,
            open   = EXCLUDED.open,
            high   = EXCLUDED.high,
            low    = EXCLUDED.low,
            close  = EXCLUDED.close,
            volume = EXCLUDED.volume
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    data["ticker"],
                    data["region"],
                    data["timestamp"],
                    data["open"],
                    data["high"],
                    data["low"],
                    data["close"],
                    data["volume"],
                ),
            )
        conn.commit()


@task(
    name="backfill-if-needed",
    retries=2,
    retry_delay_seconds=30,
    description="Check row count; if below threshold, fetch max history and upsert.",
)
def backfill_if_needed(ticker: str, region: str, yf_symbol: str) -> None:
    """
    Backfill a ticker's price history when the DB has fewer than
    ``MIN_HISTORY_ROWS`` daily rows.
    """
    log = get_run_logger()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM price_daily WHERE ticker = %s",
                (ticker,),
            )
            row = cur.fetchone()
            existing: int = row["cnt"] if row else 0

    if existing >= MIN_HISTORY_ROWS:
        return

    log.info(
        "%s has %d rows (need %d) — backfilling max history",
        ticker,
        existing,
        MIN_HISTORY_ROWS,
    )
    full_df = fetch_yfinance_daily.fn(yf_symbol, period="max")  # direct call, no Prefect wrapper
    if full_df is not None and not full_df.empty:
        upsert_daily_prices.fn(ticker, region, full_df)


def _safe_float(value: Any) -> float | None:
    """Cast *value* to ``float``; return ``None`` for NaN / None."""
    if value is None or pd.isna(value):
        return None
    return float(value)


@task(
    name="run-inference-and-persist",
    retries=1,
    retry_delay_seconds=5,
    description="Compute features, run four XGBoost models, persist analysis row.",
)
def run_inference_and_persist(ticker: str, region: str, daily_df: pd.DataFrame) -> None:
    """
    Feature-engineer, run four-model XGBoost inference, and upsert results
    into ``analysis_info``.
    """
    log = get_run_logger()

    features = engineer_features(daily_df)
    indicators = calculate_indicators(daily_df)

    predictor = FourModelPredictor()
    model_probs, model_contribs = predictor.predict_from_ohlcv(daily_df)

    for mkey, mprob in model_probs.items():
        if mprob is not None:
            log.info("  %s [%s] P(up) = %.4f", ticker, mkey, mprob)

    def _contrib_json(key: str) -> str | None:
        c = model_contribs.get(key)
        return json.dumps(c) if c else None

    if indicators.empty:
        log.warning("%s — indicators are empty; skipping analysis upsert", ticker)
        return

    latest_idx = indicators.index[-1]
    latest_date: date = daily_df.loc[latest_idx, "Date"].date()
    latest_features = features.loc[latest_idx] if latest_idx in features.index else None

    query = """
        INSERT INTO analysis_info (
            ticker, region, date, rsi, macd, macd_signal, macd_hist,
            bb_upper, bb_middle, bb_lower,
            prob_active_1w, prob_conservative_1mo,
            prob_conservative_6mo, prob_experimental,
            features_active_1w, features_conservative_1mo,
            features_conservative_6mo, features_experimental
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (ticker, date) DO UPDATE SET
            region                   = EXCLUDED.region,
            rsi                      = EXCLUDED.rsi,
            macd                     = EXCLUDED.macd,
            macd_signal              = EXCLUDED.macd_signal,
            macd_hist                = EXCLUDED.macd_hist,
            bb_upper                 = EXCLUDED.bb_upper,
            bb_middle                = EXCLUDED.bb_middle,
            bb_lower                 = EXCLUDED.bb_lower,
            prob_active_1w           = EXCLUDED.prob_active_1w,
            prob_conservative_1mo    = EXCLUDED.prob_conservative_1mo,
            prob_conservative_6mo    = EXCLUDED.prob_conservative_6mo,
            prob_experimental        = EXCLUDED.prob_experimental,
            features_active_1w       = EXCLUDED.features_active_1w,
            features_conservative_1mo = EXCLUDED.features_conservative_1mo,
            features_conservative_6mo = EXCLUDED.features_conservative_6mo,
            features_experimental    = EXCLUDED.features_experimental
    """
    params = (
        ticker,
        region,
        latest_date,
        _safe_float(indicators.loc[latest_idx, "RSI"]) if "RSI" in indicators.columns else None,
        _safe_float(indicators.loc[latest_idx, "MACD"]) if "MACD" in indicators.columns else None,
        _safe_float(indicators.loc[latest_idx, "MACD_signal"]) if "MACD_signal" in indicators.columns else None,
        _safe_float(indicators.loc[latest_idx, "MACD_hist"]) if "MACD_hist" in indicators.columns else None,
        _safe_float(latest_features["bb_upper"]) if latest_features is not None else None,
        _safe_float(latest_features["bb_middle"]) if latest_features is not None else None,
        _safe_float(latest_features["bb_lower"]) if latest_features is not None else None,
        model_probs.get("active_1w"),
        model_probs.get("conservative_1mo"),
        model_probs.get("conservative_6mo"),
        model_probs.get("experimental"),
        _contrib_json("active_1w"),
        _contrib_json("conservative_1mo"),
        _contrib_json("conservative_6mo"),
        _contrib_json("experimental"),
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
        conn.commit()
    log.info("%s — analysis row persisted for %s", ticker, latest_date)


# ──────────────────────────────────────────────────────────────────────────────
# Sub-flow: process a single ticker
# ──────────────────────────────────────────────────────────────────────────────


@flow(
    name="process-single-ticker",
    log_prints=True,
    retries=1,
    retry_delay_seconds=30,
)
def process_single_ticker(ticker: str, region: str, include_realtime: bool = True) -> None:
    """
    End-to-end processing for one ticker:
    backfill → fetch daily → upsert → realtime → inference.
    """
    log = get_run_logger()
    yf_sym = to_yf_symbol(ticker, region)
    log.info("Processing %s (yf: %s)", ticker, yf_sym)

    # 1. Backfill sparse tickers
    backfill_if_needed(ticker, region, yf_sym)

    # 2. Incremental daily fetch (last 3 months)
    daily_df = fetch_yfinance_daily(yf_sym, period="3mo")
    if daily_df is not None and not daily_df.empty:
        upsert_daily_prices(ticker, region, daily_df)
        run_inference_and_persist(ticker, region, daily_df)

    # 3. Realtime snapshot (optional — only during trading hours)
    if include_realtime:
        rt_data = fetch_yfinance_realtime(yf_sym)
        if rt_data is not None:
            # Override the ticker/region keys so DB stores the raw symbol
            rt_data["ticker"] = ticker
            rt_data["region"] = region
            upsert_realtime_price(rt_data)


# ──────────────────────────────────────────────────────────────────────────────
# Top-level Flows (deployed via prefect.yaml)
# ──────────────────────────────────────────────────────────────────────────────


@flow(
    name="krx-realtime-flow",
    log_prints=True,
    description=(
        "High-frequency ingestion during KRX trading hours. "
        "Runs every 5 minutes Mon–Fri 09:00–15:30 JST."
    ),
)
def krx_realtime_flow() -> None:
    """Fetch realtime snapshots + incremental daily for all active tickers."""
    log = get_run_logger()
    tickers = fetch_active_tickers()
    if not tickers:
        log.warning("No active tickers — nothing to do")
        return

    log.info("KRX realtime cycle — %d tickers", len(tickers))
    for t in tickers:
        process_single_ticker(t["symbol"], t["region"], include_realtime=True)
    log.info("KRX realtime cycle complete")


@flow(
    name="daily-batch-flow",
    log_prints=True,
    description=(
        "End-of-day batch ingestion. Runs once daily at 18:00 JST "
        "after all major markets have closed."
    ),
)
def daily_batch_flow() -> None:
    """Run full ingestion + inference for every active ticker (no realtime)."""
    log = get_run_logger()
    tickers = fetch_active_tickers()
    if not tickers:
        log.warning("No active tickers — nothing to do")
        return

    log.info("Daily batch cycle — %d tickers", len(tickers))
    for t in tickers:
        process_single_ticker(t["symbol"], t["region"], include_realtime=False)
    log.info("Daily batch cycle complete")


# ──────────────────────────────────────────────────────────────────────────────
# CLI convenience (``python -m ingestion.flows``)
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    daily_batch_flow()
