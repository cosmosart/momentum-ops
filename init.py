#!/usr/bin/env python3
"""
Initialization script for momentum-ops.
Sets up the database and runs initial data ingestion.
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database.db import Database
from ingestion.fetcher import DataFetcher
from dotenv import load_dotenv

# Load environment
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_database():
    """Initialize database schema."""
    logger.info("Initializing database...")
    
    db = Database()
    
    # Wait for database to be ready
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        if db.connect():
            logger.info("Database connection successful")
            break
        logger.warning(f"Database not ready, retrying... ({retry_count + 1}/{max_retries})")
        time.sleep(2)
        retry_count += 1
    
    if retry_count >= max_retries:
        logger.error("Failed to connect to database after maximum retries")
        return False
    
    # Execute schema
    schema_path = Path(__file__).parent / "database" / "schema.sql"
    if schema_path.exists():
        if getattr(db, "conn", None) is None:
            logger.error("Database connection is not established; cannot execute schema")
            db.close()
            return False
        db.execute_schema(str(schema_path))
        logger.info("Database schema initialized successfully")
    else:
        logger.warning(f"Schema file not found at {schema_path}")
    
    db.close()
    return True


def initial_data_fetch():
    """Perform initial data fetch for default ticker."""
    ticker = os.getenv('DEFAULT_TICKER', 'AAPL')
    logger.info(f"Fetching initial data for {ticker}...")
    
    db = Database()
    db.connect()
    
    try:
        fetcher = DataFetcher(ticker)
        
        # Fetch daily data
        daily_data = fetcher.fetch_daily_data(period="1y")
        
        if daily_data is not None and not daily_data.empty:
            for _, row in daily_data.iterrows():
                db.insert_daily_price(
                    ticker=ticker,
                    date_val=row['Date'].date(),
                    open_price=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    adj_close=float(row['Close']),
                    volume=int(row['Volume'])
                )
            logger.info(f"Successfully loaded {len(daily_data)} days of data for {ticker}")
        else:
            logger.warning(f"No data available for {ticker}")
    
    except Exception as e:
        logger.error(f"Error during initial data fetch: {e}")
    
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting momentum-ops initialization...")
    
    if initialize_database():
        logger.info("Database initialized successfully")
        initial_data_fetch()
        logger.info("Initialization complete!")
    else:
        logger.error("Database initialization failed")
        sys.exit(1)
