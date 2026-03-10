"""
Scheduler module using APScheduler.

Runs periodic data ingestion → feature engineering → XGBoost inference.
All training has been removed; four pre-trained XGBoost models are loaded
once at startup and re-used for every inference cycle.

When a ticker is first seen (or has insufficient history), the scheduler
automatically backfills maximum available data from yfinance before
switching to the normal incremental 3-month fetch.
"""

import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
import pandas as pd

import json as _json

from database.db import Database
from ingestion.fetcher import DataFetcher
from models.models import calculate_indicators, FourModelPredictor
from models.features import engineer_features
from shared.config import to_yf_symbol

from prefect.deployments import Deployment
from prefect.server.schemas.schedules import CronSchedule
from .flows import kr_minute_ingestion_flow

load_dotenv()

logger = logging.getLogger(__name__)

# Minimum number of daily rows required for reliable feature engineering.
# RSI needs 14, MACD needs 26+9, Bollinger needs 20, lagged-return needs 10,
# and the XGBoost model was trained on tickers with ≥60 rows.
# 200 gives comfortable headroom for all indicators + a few months of history.
MIN_HISTORY_ROWS = 200


class DataScheduler:
    """Manages scheduled data updates and XGBoost inference."""
    
    def __init__(self, tickers: list = None):
        """
        Initialize DataScheduler.
        
        Args:
            tickers: List of ticker symbols to track
        """
        self.tickers = tickers or [os.getenv('DEFAULT_TICKER', 'AAPL')]
        self.scheduler = BackgroundScheduler(
            timezone=os.getenv('SCHEDULER_TIMEZONE', 'UTC')
        )
        self.db = Database()
        # Load four targeted strategy models (lazy-loaded on first use)
        self.predictor = FourModelPredictor()
        logger.info("FourModelPredictor initialized (lazy-load on first use)")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_db(self) -> bool:
        """Return True if the DB connection is alive, reconnecting if needed."""
        if not self.db.conn or (hasattr(self.db.conn, 'closed') and self.db.conn.closed):
            return self.db.connect()
        return True

    @staticmethod
    def _safe_float(value):
        """Convert a value to float, returning None for NaN / None."""
        if value is None or pd.isna(value):
            return None
        return float(value)

    def _bulk_upsert_daily(self, ticker: str, region: str, df: pd.DataFrame) -> int:
        """
        Batch-upsert daily rows in a single transaction.

        Returns the number of rows written.
        """
        rows = [
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
        try:
            with self.db.conn.cursor() as cur:
                cur.executemany(query, rows)
            self.db.conn.commit()
            return len(rows)
        except Exception as e:
            logger.error("Bulk upsert failed for %s: %s", ticker, e)
            if self.db.conn and not self.db.conn.closed:
                self.db.conn.rollback()
            return 0

    # ------------------------------------------------------------------
    # Backfill
    # ------------------------------------------------------------------

    def _backfill_if_needed(self, ticker: str, region: str, yf_symbol: str) -> None:
        """
        Check the DB row count for *ticker*.  If it is below
        ``MIN_HISTORY_ROWS``, download the maximum available history
        from yfinance and bulk-upsert it.
        """
        existing = self.db.get_ticker_record_count(ticker)
        if existing >= MIN_HISTORY_ROWS:
            return  # plenty of data — skip

        logger.info(
            "  %s has only %d rows (need %d) — backfilling max history …",
            ticker, existing, MIN_HISTORY_ROWS,
        )
        fetcher = DataFetcher(yf_symbol)
        full_history = fetcher.fetch_daily_data(period="max")

        if full_history is None or full_history.empty:
            logger.warning("  %s — yfinance returned no data for period='max'", ticker)
            return

        count = self._bulk_upsert_daily(ticker, region, full_history)
        logger.info(
            "  %s backfill complete — %d rows  [%s → %s]",
            ticker,
            count,
            full_history["Date"].iloc[0].date(),
            full_history["Date"].iloc[-1].date(),
        )

    # ------------------------------------------------------------------
    # Per-ticker update
    # ------------------------------------------------------------------

    def update_data(self, ticker: str, region: str = "US"):
        """
        Update data for a single ticker: ingest prices, compute indicators,
        run XGBoost inference, and persist results.
        
        Args:
            ticker: Raw stock ticker symbol (no yfinance suffix)
            region: Market region code (US, KR, JP, GLOBAL)
        """
        yf_symbol = to_yf_symbol(ticker, region)
        logger.info(f"Updating data for {ticker} (yf={yf_symbol})")
        
        try:
            if not self._ensure_db():
                logger.error("Database connection failed; aborting update for %s", ticker)
                return

            # ── Backfill if this ticker is new or has sparse data ─────
            self._backfill_if_needed(ticker, region, yf_symbol)

            # ── Incremental fetch (last 3 months) ────────────────────
            fetcher = DataFetcher(yf_symbol)

            # Fetch and store realtime data
            realtime_data = fetcher.fetch_realtime_data()
            if realtime_data:
                self.db.insert_realtime_price(
                    ticker=realtime_data['ticker'],
                    timestamp=realtime_data['timestamp'],
                    open_price=realtime_data['open'],
                    high=realtime_data['high'],
                    low=realtime_data['low'],
                    close=realtime_data['close'],
                    volume=realtime_data['volume'],
                    region=region,
                )
                logger.info(f"Inserted realtime data for {ticker}")
            
            # Fetch recent daily data for indicator computation
            daily_data = fetcher.fetch_daily_data(period="3mo")
            if daily_data is not None and not daily_data.empty:
                # Upsert last 3 months (fast — small batch)
                self._bulk_upsert_daily(ticker, region, daily_data)

                # ── Feature engineering (shared with training) ────────
                features = engineer_features(daily_data)
                indicators = calculate_indicators(daily_data)

                # ── Four-model inference (single feature pass) ────────
                model_probs, model_contribs = self.predictor.predict_from_ohlcv(daily_data)
                for mkey, mprob in model_probs.items():
                    if mprob is not None:
                        logger.info("  %s  [%s] P(up) = %.4f", ticker, mkey, mprob)

                # Serialise SHAP contributions to JSON strings for JSONB columns
                def _contrib_json(key: str) -> str | None:
                    c = model_contribs.get(key)
                    return _json.dumps(c) if c else None

                # ── Persist analysis row ──────────────────────────────
                if not indicators.empty:
                    latest_idx = indicators.index[-1]
                    latest_date = daily_data.loc[latest_idx, 'Date'].date()
                    latest_features = features.loc[latest_idx] if latest_idx in features.index else None

                    self.db.insert_analysis(
                        ticker=ticker,
                        date_val=latest_date,
                        rsi=self._safe_float(indicators.loc[latest_idx, 'RSI']) if 'RSI' in indicators.columns else None,
                        macd=self._safe_float(indicators.loc[latest_idx, 'MACD']) if 'MACD' in indicators.columns else None,
                        macd_signal=self._safe_float(indicators.loc[latest_idx, 'MACD_signal']) if 'MACD_signal' in indicators.columns else None,
                        macd_hist=self._safe_float(indicators.loc[latest_idx, 'MACD_hist']) if 'MACD_hist' in indicators.columns else None,
                        bb_upper=self._safe_float(latest_features['bb_upper']) if latest_features is not None else None,
                        bb_lower=self._safe_float(latest_features['bb_lower']) if latest_features is not None else None,
                        bb_middle=self._safe_float(latest_features['bb_middle']) if latest_features is not None else None,
                        prob_active_1w=model_probs.get("active_1w"),
                        prob_conservative_1mo=model_probs.get("conservative_1mo"),
                        prob_conservative_6mo=model_probs.get("conservative_6mo"),
                        prob_experimental=model_probs.get("experimental"),
                        features_active_1w=_contrib_json("active_1w"),
                        features_conservative_1mo=_contrib_json("conservative_1mo"),
                        features_conservative_6mo=_contrib_json("conservative_6mo"),
                        features_experimental=_contrib_json("experimental"),
                        region=region,
                    )
                    logger.info(f"Inserted analysis data for {ticker}")
                
        except Exception as e:
            logger.error(f"Failed to update data for {ticker}: {e}")
    

    def run_ingestion_cycle(self):
        """
        The Master Job:
        1. Asks DB: "What should I track right now?"
        2. Loops through that list.
        3. For each ticker, backfills if needed, then runs the normal update.
        """
        logger.info("Starting ingestion cycle...")
        
        if not self._ensure_db():
            logger.error("Database connection failed; aborting ingestion cycle")
            return
        
        # dynamic_tickers will contain ONLY the rows where is_active = true
        dynamic_tickers = self.db.get_active_tickers()  # list[dict]
        
        if not dynamic_tickers:
            logger.warning("No active tickers found in database.")
            return

        for t in dynamic_tickers:
            self.update_data(t["symbol"], t["region"])
            
    def start(self):
        """Start the scheduler."""
        # Schedule the master ingestion job
        update_interval = int(os.getenv('UPDATE_INTERVAL_MINUTES', 30))
        
        self.scheduler.add_job(
            func=self.run_ingestion_cycle,
            trigger=IntervalTrigger(minutes=update_interval),
            id='master_ingestion_job',
            name='Master Ingestion Cycle',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info(f"Scheduler started. Running every {update_interval} minutes.")
        
        # Run immediately on startup
        logger.info("Running initial ingestion cycle...")
        self.run_ingestion_cycle()
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        self.db.close()
        logger.info("Scheduler stopped")

# Runs every 3 minutes from 09:00 to 15:00, Monday through Friday.
# (Note: You may want an explicit trigger for the 15:00-15:30 window depending on how aggressive the closing cross trades are for your strategy).
kr_market_schedule = CronSchedule(
    cron="*/5 9-15 * * 1-5", 
    timezone="Asia/Seoul"
)

deployment = Deployment.build_from_flow(
    flow=kr_minute_ingestion_flow,
    name="kr-swing-5min-ingestion",
    parameters={"tickers": ["069500",
                            "122630",
                            "229200"]}, # E.g., Samsung, SK Hynix, Hanmi Semi
    schedule=kr_market_schedule,
    work_queue_name="default"
)

if __name__ == "__main__":
    deployment.apply()