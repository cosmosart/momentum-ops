"""
Scheduler module using APScheduler.
Schedules periodic data updates.
"""

import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
import pandas as pd

from database.db import Database
from ingestion.fetcher import DataFetcher
from models.models import calculate_indicators, generate_predictions

load_dotenv()

logger = logging.getLogger(__name__)


class DataScheduler:
    """Manages scheduled data updates."""
    
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
        
    def update_data(self, ticker: str):
        """
        Update data for a single ticker.
        
        Args:
            ticker: Stock ticker symbol
        """
        logger.info(f"Updating data for {ticker}")
        
        try:
            # Connect to database
            if not self.db.conn or (hasattr(self.db.conn, 'closed') and self.db.conn.closed):
                if not self.db.connect():
                    logger.error("Database connection failed; aborting update for %s", ticker)
                    return
            
            # Fetch data
            fetcher = DataFetcher(ticker)
            
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
                    volume=realtime_data['volume']
                )
                logger.info(f"Inserted realtime data for {ticker}")
            
            # Fetch and store daily data
            # Use longer period to ensure sufficient data for RSI (14) and MACD (26)
            daily_data = fetcher.fetch_daily_data(period="3mo")
            if daily_data is not None and not daily_data.empty:
                for _, row in daily_data.iterrows():
                    self.db.insert_daily_price(
                        ticker=ticker,
                        date_val=row['Date'].date(),
                        open_price=float(row['Open']),
                        high=float(row['High']),
                        low=float(row['Low']),
                        close=float(row['Close']),
                        adj_close=float(row['Close']),  # yfinance returns adjusted close by default
                        volume=int(row['Volume'])
                    )
                
                # Calculate indicators
                indicators = calculate_indicators(daily_data)
                
                # Generate predictions
                predictions = generate_predictions(daily_data)
                
                # Store analysis data (most recent)
                if not indicators.empty:
                    latest_idx = indicators.index[-1]
                    latest_date = daily_data.loc[latest_idx, 'Date'].date()
                    
                    # Helper function to safely convert to float, handling NaN
                    def safe_float(value):
                        if pd.isna(value):
                            return None
                        return float(value)
                    
                    self.db.insert_analysis(
                        ticker=ticker,
                        date_val=latest_date,
                        rsi=safe_float(indicators.loc[latest_idx, 'RSI']) if 'RSI' in indicators.columns else None,
                        macd=safe_float(indicators.loc[latest_idx, 'MACD']) if 'MACD' in indicators.columns else None,
                        macd_signal=safe_float(indicators.loc[latest_idx, 'MACD_signal']) if 'MACD_signal' in indicators.columns else None,
                        macd_hist=safe_float(indicators.loc[latest_idx, 'MACD_hist']) if 'MACD_hist' in indicators.columns else None,
                        prediction_1d=predictions.get('1d'),
                        prediction_1w=predictions.get('1w'),
                        prediction_1m=predictions.get('1m'),
                        prediction_1y=predictions.get('1y')
                    )
                    logger.info(f"Inserted analysis data for {ticker}")
                
        except Exception as e:
            logger.error(f"Failed to update data for {ticker}: {e}")
    

    def run_ingestion_cycle(self):
        """
        The Master Job:
        1. Asks DB: "What should I track right now?"
        2. Loops through that list.
        3. Updates data.
        """
        logger.info("Starting ingestion cycle...")
        
        # Ensure database connection
        if not self.db.conn or (hasattr(self.db.conn, 'closed') and self.db.conn.closed):
            if not self.db.connect():
                logger.error("Database connection failed; aborting ingestion cycle")
                return
        
        # dynamic_tickers will contain ONLY the rows where is_active = true
        dynamic_tickers = self.db.get_active_tickers()
        
        if not dynamic_tickers:
            logger.warning("No active tickers found in database.")
            return

        for ticker in dynamic_tickers:
            self.update_data(ticker) # Your existing update logic
            
    def start(self):
        """Start the scheduler."""
        # Schedule the master ingestion job
        update_interval = int(os.getenv('UPDATE_INTERVAL_MINUTES', 5))
        
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
