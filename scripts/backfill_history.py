#!/usr/bin/env python3
"""
One-time script to backfill maximum available historical data from yfinance.
Run this locally before re-training your XGBoost model.

Usage:
    python scripts/backfill_history.py              # all active tickers
    python scripts/backfill_history.py AAPL MSFT    # specific tickers only
"""

import argparse
import os
import sys
import time
import logging
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.db import Database
from ingestion.fetcher import DataFetcher
from shared.config import to_yf_symbol

load_dotenv(PROJECT_ROOT / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill")


def _bulk_upsert(db: Database, ticker: str, region: str, df: pd.DataFrame) -> int:
    """
    Batch-upsert daily rows inside a single transaction instead of
    committing per row.  Falls back to row-by-row on conflict errors.

    Returns the number of rows written.
    """
    rows = []
    for _, r in df.iterrows():
        rows.append((
            ticker,
            region,
            r["Date"].date(),
            float(r["Open"]),
            float(r["High"]),
            float(r["Low"]),
            float(r["Close"]),
            float(r["Close"]),   # adj_close — yfinance already adjusts closes
            int(r["Volume"]),
        ))

    query = """
        INSERT INTO price_daily (ticker, region, date, open, high, low, close, adj_close, volume)
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
        with db.conn.cursor() as cur:
            cur.executemany(query, rows)
        db.conn.commit()
        return len(rows)
    except Exception as e:
        logger.error("Bulk upsert failed for %s: %s — rolling back", ticker, e)
        if db.conn and not db.conn.closed:
            db.conn.rollback()
        return 0


def backfill_ticker(db: Database, symbol: str, region: str = "US") -> int:
    """
    Download full history for *symbol* and upsert into the database.

    Returns the number of rows inserted/updated.
    """
    yf_symbol = to_yf_symbol(symbol, region)
    fetcher = DataFetcher(yf_symbol)

    # period="max" pulls everything yfinance has (often 20+ years for US equities)
    daily_data = fetcher.fetch_daily_data(period="max")

    if daily_data is None or daily_data.empty:
        logger.warning("  %s — no data returned by yfinance", symbol)
        return 0

    first_date = daily_data["Date"].iloc[0].date()
    last_date = daily_data["Date"].iloc[-1].date()
    logger.info(
        "  %s — %d rows  [%s → %s]", symbol, len(daily_data), first_date, last_date
    )

    count = _bulk_upsert(db, symbol, region, daily_data)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill maximum available daily history from yfinance into PostgreSQL."
    )
    parser.add_argument(
        "tickers",
        nargs="*",
        help="Specific ticker symbols to backfill (default: all active tickers from DB).",
    )
    args = parser.parse_args()

    db = Database()
    if not db.connect():
        logger.error("Failed to connect to DB.")
        sys.exit(1)

    try:
        if args.tickers:
            # CLI args are treated as yfinance-style symbols with US region default
            ticker_entries = [
                {"symbol": t.upper(), "region": "US"} for t in args.tickers
            ]
            logger.info("Backfilling %d ticker(s) from CLI args", len(ticker_entries))
        else:
            ticker_entries = db.get_active_tickers()  # returns list[dict]
            if not ticker_entries:
                logger.warning("No active tickers found in the database.")
                sys.exit(0)
            logger.info("Backfilling %d active ticker(s) from database", len(ticker_entries))

        total_rows = 0
        failed: list[str] = []
        t0 = time.perf_counter()

        for i, entry in enumerate(ticker_entries, start=1):
            symbol = entry["symbol"]
            region = entry["region"]
            logger.info("[%d/%d] %s (region=%s)", i, len(ticker_entries), symbol, region)
            try:
                count = backfill_ticker(db, symbol, region)
                total_rows += count
            except Exception as e:
                logger.error("  %s — FAILED: %s", symbol, e)
                failed.append(symbol)
                # Ensure the connection is still usable for the next ticker
                if db.conn and not db.conn.closed:
                    db.conn.rollback()

        elapsed = time.perf_counter() - t0

        # Summary
        logger.info("─" * 50)
        logger.info(
            "Backfill complete — %d rows across %d tickers in %.1fs",
            total_rows,
            len(ticker_entries) - len(failed),
            elapsed,
        )
        if failed:
            logger.warning("Failed tickers: %s", ", ".join(failed))
        logger.info("You are ready to run:  python scripts/train_local.py --tune")

    finally:
        db.close()


if __name__ == "__main__":
    main()