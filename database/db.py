""" Database module for momentum-ops application.
Handles database connections and operations.
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get module-level logger (configuration is handled by application entry points)
logger = logging.getLogger(__name__)


class Database:
    """Database connection and operations manager."""
    
    def __init__(self):
        """Initialize database connection parameters."""
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = os.getenv('DB_PORT', '5432')
        self.database = os.getenv('DB_NAME', 'momentum_db')
        self.user = os.getenv('DB_USER', 'momentum_user')
        self.password = os.getenv('DB_PASSWORD', 'momentum_password')
        self.conn = None
        
    def connect(self) -> bool:
        """
        Establish database connection.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.conn = psycopg.connect(
                host=self.host,
                port=self.port,
                dbname=self.database,
                user=self.user,
                password=self.password
            )
            logger.info("Database connection established successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def execute_schema(self, schema_path: str):
        """
        Execute SQL schema file to create tables.
        
        Args:
            schema_path: Path to schema.sql file
        """
        try:
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
            
            with self.conn.cursor() as cursor:
                cursor.execute(schema_sql)
                self.conn.commit()
                logger.info("Database schema executed successfully")
        except Exception as e:
            logger.error(f"Failed to execute schema: {e}")
            self.conn.rollback()
    
    def insert_realtime_price(self, ticker: str, timestamp: datetime, 
                             open_price: float, high: float, low: float, 
                             close: float, volume: int):
        """
        Insert real-time price data.
        
        Args:
            ticker: Stock ticker symbol
            timestamp: Price timestamp
            open_price: Opening price
            high: High price
            low: Low price
            close: Closing price
            volume: Trading volume
        """
        query = """
        INSERT INTO price_realtime (ticker, timestamp, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, timestamp) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, (ticker, timestamp, open_price, high, low, close, volume))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to insert realtime price: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
    
    def insert_daily_price(self, ticker: str, date_val: date, 
                          open_price: float, high: float, low: float, 
                          close: float, adj_close: float, volume: int):
        """
        Insert daily price data.
        
        Args:
            ticker: Stock ticker symbol
            date_val: Price date
            open_price: Opening price
            high: High price
            low: Low price
            close: Closing price
            adj_close: Adjusted closing price
            volume: Trading volume
        """
        query = """
        INSERT INTO price_daily (ticker, date, open, high, low, close, adj_close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, date) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            adj_close = EXCLUDED.adj_close,
            volume = EXCLUDED.volume
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, (ticker, date_val, open_price, high, low, close, adj_close, volume))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to insert daily price: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
    
    def insert_analysis(self, ticker: str, date_val: date, rsi: Optional[float] = None,
                       macd: Optional[float] = None, macd_signal: Optional[float] = None,
                       macd_hist: Optional[float] = None, prediction_1d: Optional[float] = None,
                       prediction_1w: Optional[float] = None, prediction_1m: Optional[float] = None,
                       prediction_1y: Optional[float] = None):
        """
        Insert analysis data.
        
        Args:
            ticker: Stock ticker symbol
            date_val: Analysis date
            rsi: RSI indicator value
            macd: MACD indicator value
            macd_signal: MACD signal value
            macd_hist: MACD histogram value
            prediction_1d: 1-day prediction
            prediction_1w: 1-week prediction
            prediction_1m: 1-month prediction
            prediction_1y: 1-year prediction
        """
        query = """
        INSERT INTO analysis_info (ticker, date, rsi, macd, macd_signal, macd_hist,
                                  prediction_1d, prediction_1w, prediction_1m, prediction_1y)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, date) DO UPDATE SET
            rsi = EXCLUDED.rsi,
            macd = EXCLUDED.macd,
            macd_signal = EXCLUDED.macd_signal,
            macd_hist = EXCLUDED.macd_hist,
            prediction_1d = EXCLUDED.prediction_1d,
            prediction_1w = EXCLUDED.prediction_1w,
            prediction_1m = EXCLUDED.prediction_1m,
            prediction_1y = EXCLUDED.prediction_1y
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, (ticker, date_val, rsi, macd, macd_signal, macd_hist,
                                      prediction_1d, prediction_1w, prediction_1m, prediction_1y))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to insert analysis: {e}")
            if self.conn and not self.conn.closed:
                self.conn.rollback()
    
    def get_daily_prices(self, ticker: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve daily prices for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of records to retrieve
            
        Returns:
            List of price records as dictionaries
        """
        query = """
        SELECT * FROM price_daily
        WHERE ticker = %s
        ORDER BY date DESC
        LIMIT %s
        """
        try:
            with self.conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, (ticker, limit))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get daily prices: {e}")
            return []
    
    def get_analysis(self, ticker: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve analysis data for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            limit: Maximum number of records to retrieve
            
        Returns:
            List of analysis records as dictionaries
        """
        query = """
        SELECT * FROM analysis_info
        WHERE ticker = %s
        ORDER BY date DESC
        LIMIT %s
        """
        try:
            with self.conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, (ticker, limit))
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get analysis: {e}")
            return []

    def get_active_tickers(self) -> List[str]:
        """Fetch all tickers marked as active."""
        query = "SELECT symbol FROM tickers WHERE is_active = true"
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query)
                # Return a simple list like ['AAPL', '1542.T']
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch active tickers: {e}")
            return []

    def add_ticker(self, symbol: str):
        """Add a new ticker or reactivate an existing one."""
        query = """
        INSERT INTO tickers (symbol, is_active) 
        VALUES (%s, true)
        ON CONFLICT (symbol) DO UPDATE SET is_active = true
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, (symbol,))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to add ticker {symbol}: {e}")
            self.conn.rollback()

    def deactivate_ticker(self, symbol: str):
        """Stop tracking a ticker (Soft Delete). Data remains."""
        query = "UPDATE tickers SET is_active = false WHERE symbol = %s"
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, (symbol,))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to deactivate ticker {symbol}: {e}")
            self.conn.rollback()