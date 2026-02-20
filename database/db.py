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
    
    def insert_analysis(
        self,
        ticker: str,
        date_val: date,
        rsi: Optional[float] = None,
        macd: Optional[float] = None,
        macd_signal: Optional[float] = None,
        macd_hist: Optional[float] = None,
        bb_upper: Optional[float] = None,
        bb_middle: Optional[float] = None,
        bb_lower: Optional[float] = None,
        prob_active_1w: Optional[float] = None,
        prob_conservative_1mo: Optional[float] = None,
        prob_conservative_6mo: Optional[float] = None,
        prob_experimental: Optional[float] = None,
        features_active_1w: Optional[str] = None,
        features_conservative_1mo: Optional[str] = None,
        features_conservative_6mo: Optional[str] = None,
        features_experimental: Optional[str] = None,
    ):
        """
        Insert analysis data (indicators + directional probabilities + SHAP contributions).

        Args:
            ticker: Stock ticker symbol
            date_val: Analysis date
            rsi: RSI (14) value
            macd: MACD line value
            macd_signal: MACD signal line value
            macd_hist: MACD histogram value
            bb_upper: Bollinger Band upper
            bb_middle: Bollinger Band middle (SMA 20)
            bb_lower: Bollinger Band lower
            prob_active_1w: Active 1-week probability
            prob_conservative_1mo: Conservative 1-month probability
            prob_conservative_6mo: Conservative 6-month probability
            prob_experimental: Experimental sandbox probability
            features_active_1w: JSON string of top-3 SHAP contributions (active 1w)
            features_conservative_1mo: JSON string of top-3 SHAP contributions (conservative 1mo)
            features_conservative_6mo: JSON string of top-3 SHAP contributions (conservative 6mo)
            features_experimental: JSON string of top-3 SHAP contributions (experimental)
        """
        query = """
        INSERT INTO analysis_info (
            ticker, date, rsi, macd, macd_signal, macd_hist,
            bb_upper, bb_middle, bb_lower,
            prob_active_1w, prob_conservative_1mo,
            prob_conservative_6mo, prob_experimental,
            features_active_1w, features_conservative_1mo,
            features_conservative_6mo, features_experimental
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (ticker, date) DO UPDATE SET
            rsi = EXCLUDED.rsi,
            macd = EXCLUDED.macd,
            macd_signal = EXCLUDED.macd_signal,
            macd_hist = EXCLUDED.macd_hist,
            bb_upper = EXCLUDED.bb_upper,
            bb_middle = EXCLUDED.bb_middle,
            bb_lower = EXCLUDED.bb_lower,
            prob_active_1w = EXCLUDED.prob_active_1w,
            prob_conservative_1mo = EXCLUDED.prob_conservative_1mo,
            prob_conservative_6mo = EXCLUDED.prob_conservative_6mo,
            prob_experimental = EXCLUDED.prob_experimental,
            features_active_1w = EXCLUDED.features_active_1w,
            features_conservative_1mo = EXCLUDED.features_conservative_1mo,
            features_conservative_6mo = EXCLUDED.features_conservative_6mo,
            features_experimental = EXCLUDED.features_experimental
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        ticker, date_val, rsi, macd, macd_signal, macd_hist,
                        bb_upper, bb_middle, bb_lower,
                        prob_active_1w, prob_conservative_1mo,
                        prob_conservative_6mo, prob_experimental,
                        features_active_1w, features_conservative_1mo,
                        features_conservative_6mo, features_experimental,
                    ),
                )
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
        query = "SELECT symbol FROM tickers WHERE is_active = true ORDER BY symbol"
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query)
                # Return a simple list like ['AAPL', '1542.T']
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch active tickers: {e}")
            return []

    def get_all_tickers(self) -> List[str]:
        """Fetch all tickers from the database."""
        query = "SELECT symbol FROM tickers ORDER BY symbol"
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query)
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch all tickers: {e}")
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

    def get_ticker_record_count(self, ticker: str) -> int:
        """Returns the number of historical daily price rows for a specific ticker."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM price_daily WHERE ticker = %s", (ticker,))
                result = cur.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error checking record count for {ticker}: {e}")
            return 0