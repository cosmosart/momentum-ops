"""
Standalone backfill script for kr_minute_ohlcv.

Fetches the maximum allowable 1-minute historical data (7 days) via yfinance
for all active KR tickers and safely injects it into PostgreSQL. 
Uses native psycopg3 executemany for high-performance batch insertion and strictly 
enforces Asia/Seoul timezone localization to align with the KIS live data pipeline.
"""

import os
import sys
import logging
import pandas as pd
import yfinance as yf

# Ensure the script can find your project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database
from shared.config import to_yf_symbol

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def backfill_1m_ticker(ticker: str, region: str = "KR") -> None:
    yf_symbol = to_yf_symbol(ticker, region)
    logger.info(f"Fetching 7-day 1-minute seed data for {ticker} ({yf_symbol})...")
    
    # yfinance max limit for 1m data is exactly 7d
    ticker_obj = yf.Ticker(yf_symbol)
    df = ticker_obj.history(period="7d", interval="1m")
    
    if df.empty:
        logger.warning(f"No 1m data returned from yfinance for {yf_symbol}.")
        return
        
    # Standardize index and timezone
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert('Asia/Seoul')
    else:
        df.index = df.index.tz_convert('Asia/Seoul')
        
    df = df.reset_index()
    date_col = "Datetime" if "Datetime" in df.columns else "Date"
    
    # Calculate accumulated_value proxy (Close * Volume) since yf doesn't provide it
    df['accumulated_value'] = df['Close'] * df['Volume']
    
    # Drop rows with NaN in critical columns
    df = df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume'])
    
    # Prepare tuples for high-performance batch insertion
    rows = [
        (
            ticker,
            1,  # Hardcoded to 1-minute interval
            r[date_col].to_pydatetime(), # Explicitly pass as python datetime
            float(r["Open"]),
            float(r["High"]),
            float(r["Low"]),
            float(r["Close"]),
            int(r["Volume"]),
            float(r["accumulated_value"])
        )
        for _, r in df.iterrows()
    ]
    
    # Notice the standard (%s, %s...) format required for executemany
    query = """
        INSERT INTO kr_minute_ohlcv 
            (ticker, interval_min, timestamp, open_price, high_price, low_price, close_price, volume, accumulated_value)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, interval_min, timestamp) DO NOTHING
    """
    
    db = Database()
    if not db.connect():
        logger.error(f"Failed to connect to database for {ticker}.")
        return
        
    try:
        with db.conn.cursor() as cur:
            # psycopg3 native executemany is highly optimized
            cur.executemany(query, rows)
            inserted = cur.rowcount
        db.conn.commit()
        logger.info(f"Successfully evaluated {len(rows)} 1-minute candles for {ticker}, {inserted} new rows inserted.")
    except Exception as e:
        logger.error(f"Failed to insert seed data for {ticker}: {e}")
        if db.conn and not db.conn.closed:
            db.conn.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("Starting 1-minute historical backfill sequence...")
    
    db = Database()
    if db.connect():
        # Fetch only active KR tickers
        active_tickers = [t for t in db.get_active_tickers() if t["region"] == "KR"]
        db.close()
        
        logger.info(f"Found {len(active_tickers)} active KR tickers.")
        for t in active_tickers:
            backfill_1m_ticker(t["symbol"], region=t["region"])
            
        logger.info("Backfill complete. The momentum dashboard has a 7-day baseline.")
    else:
        logger.error("Could not connect to database to fetch ticker list.")