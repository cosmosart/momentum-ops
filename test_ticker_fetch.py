#!/usr/bin/env python3
"""
Test script to verify ticker data fetching.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestion.fetcher import DataFetcher
from database.db import Database

def test_ticker(ticker_symbol):
    """Test fetching data for a specific ticker."""
    print(f"\n{'='*60}")
    print(f"Testing ticker: {ticker_symbol}")
    print('='*60)
    
    # Test fetcher
    fetcher = DataFetcher(ticker_symbol)
    
    print("\n1. Testing realtime data fetch...")
    realtime_data = fetcher.fetch_realtime_data()
    if realtime_data:
        print(f"   ✅ Success: {realtime_data}")
    else:
        print(f"   ❌ Failed to fetch realtime data")
    
    print("\n2. Testing daily data fetch...")
    daily_data = fetcher.fetch_daily_data(period="1mo")
    if daily_data is not None and not daily_data.empty:
        print(f"   ✅ Success: Got {len(daily_data)} rows")
        print(f"   Date range: {daily_data['Date'].min()} to {daily_data['Date'].max()}")
        print(f"   Columns: {list(daily_data.columns)}")
    else:
        print(f"   ❌ Failed to fetch daily data")
    
    # Check database
    print("\n3. Checking database records...")
    db = Database()
    if db.connect():
        # Check daily prices
        daily_prices = db.get_daily_prices(ticker_symbol, limit=10)
        print(f"   Daily prices in DB: {len(daily_prices)} rows")
        
        # Check analysis data
        analysis = db.get_analysis_data(ticker_symbol, limit=5)
        print(f"   Analysis records in DB: {len(analysis)} rows")
        
        db.close()
    else:
        print("   ❌ Failed to connect to database")
    
    print()

if __name__ == "__main__":
    # Test both tickers
    test_ticker("AAPL")
    test_ticker("1542.T")
