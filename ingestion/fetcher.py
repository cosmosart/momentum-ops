"""
Data fetcher module using yfinance.
Fetches market data for stocks.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import yfinance as yf
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches market data using yfinance."""
    
    def __init__(self, ticker: str):
        """
        Initialize DataFetcher.
        
        Args:
            ticker: Stock ticker symbol
        """
        self.ticker = ticker
        self.yf_ticker = yf.Ticker(ticker)
        
    def fetch_realtime_data(self) -> Optional[Dict[str, Any]]:
        """
        Fetch current/realtime data for the ticker.
        
        Returns:
            Dictionary with current price data or None if failed
        """
        try:
            # Get latest intraday data
            data = self.yf_ticker.history(period='1d', interval='1m')
            if data.empty:
                logger.warning(f"No realtime data available for {self.ticker}")
                return None
            
            latest = data.iloc[-1]
            return {
                'ticker': self.ticker,
                'timestamp': data.index[-1].to_pydatetime(),
                'open': float(latest['Open']),
                'high': float(latest['High']),
                'low': float(latest['Low']),
                'close': float(latest['Close']),
                'volume': int(latest['Volume'])
            }
        except Exception as e:
            logger.error(f"Failed to fetch realtime data for {self.ticker}: {e}")
            return None
    
    def fetch_daily_data(self, period: str = "1y") -> Optional[pd.DataFrame]:
        """
        Fetch daily historical data.
        
        Args:
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            
        Returns:
            DataFrame with daily price data or None if failed
        """
        try:
            data = self.yf_ticker.history(period=period)
            if data.empty:
                logger.warning(f"No daily data available for {self.ticker}")
                return None
            
            # Reset index to make date a column
            data = data.reset_index()
            data['ticker'] = self.ticker
            return data
        except Exception as e:
            logger.error(f"Failed to fetch daily data for {self.ticker}: {e}")
            return None
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get ticker information.
        
        Returns:
            Dictionary with ticker information
        """
        try:
            return self.yf_ticker.info
        except Exception as e:
            logger.error(f"Failed to get info for {self.ticker}: {e}")
            return {}
