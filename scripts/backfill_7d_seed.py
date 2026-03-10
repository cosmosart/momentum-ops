"""
One-off script to seed the kr_minute_ohlcv table with 7 days of historical
1-minute intraday data using yfinance. 
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

def backfill_1m_ticker(ticker: str, region: str = "KR"):
    yf_symbol = to_yf_symbol(ticker, region)
    logger.info(f"Fetching 7-day 1-minute seed data for {ticker} ({yf_symbol})...")
    
    # yfinance max limit for 1m data is exactly 7d
    ticker_obj = yf.Ticker(yf_symbol)
    df = ticker_obj.history(period="7d", interval="1m")
    
    if df.empty:
        logger.warning(f"No 1m data returned from yfinance for {yf_symbol}.")
        return
        
    # Reset index to manipulate the Datetime
    df = df.reset_index()
    date_col = "Datetime" if "Datetime" in df.columns else "Date"
    
    # Convert timezone to UTC for safe PostgreSQL insertion
    if df[date_col].dt.tz is None:
        df[date_col] = df[date_col].dt.tz_localize('UTC')
    else:
        df[date_col] = df[date_col].dt.tz_convert('UTC')
        
    # Calculate a proxy for accumulated_value (Trade Amount in KRW)
    df['accumulated_value'] = df['Close'] * df['Volume']
    
    # Prepare tuples for bulk database insertion directly from the 1m dataframe
    rows = [
        (
            ticker,
            1,  # Hardcoded to 1-minute interval
            r[date_col].to_pydatetime(),
            float(r["Open"]),
            float(r["High"]),
            float(r["Low"]),
            float(r["Close"]),
            int(r["Volume"]),
            float(r["accumulated_value"])
        )
        for _, r in df.iterrows()
    ]
    
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
            cur.executemany(query, rows)
        db.conn.commit()
        logger.info(f"Successfully seeded {len(rows)} 1-minute candles for {ticker}.")
    except Exception as e:
        logger.error(f"Failed to insert seed data for {ticker}: {e}")
        db.conn.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    db = Database()
    if db.connect():
        # Fetch active KR tickers from your database
        active_tickers = [t for t in db.get_active_tickers() if t["region"] == "KR"]
        db.close()
        
        logger.info(f"Starting 7-day 1-minute backfill for {len(active_tickers)} KR tickers...")
        for t in active_tickers:
            backfill_1m_ticker(t["symbol"], region=t["region"])
            
        logger.info("Backfill complete. 1-minute baseline established.")
    else:
        logger.error("Could not connect to database to fetch ticker list.")