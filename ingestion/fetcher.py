"""
Data fetcher module using yfinance.
Fetches market data for stocks.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import yfinance as yf
import pandas as pd
import httpx

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
            
            # CRITICAL FIX FOR TIMESTAMPTZ:
            # yfinance returns a timezone-aware index (e.g., America/New_York).
            # We convert it to UTC immediately to be safe for Postgres.
            timestamp = data.index[-1].to_pydatetime()
            
            if timestamp.tzinfo is None:
                # If yfinance somehow returns a naive timestamp, force it to UTC
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            else:
                # Convert whatever timezone yfinance gave us (e.g. EST) to UTC
                timestamp = timestamp.astimezone(timezone.utc)

            return {
                'ticker': self.ticker,
                'timestamp': timestamp,  # <--- Now safely UTC
                'open': float(latest['Open']),
                'high': float(latest['High']),
                'low': float(latest['Low']),
                'close': float(latest['Close']),
                'volume': int(latest['Volume'])
            }
        except Exception as e:
            logger.error(f"Failed to fetch realtime data: {e}")
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

class KISFetcher:
    def __init__(self, api_key: str, api_secret: str, token: str):
        self.base_url = "https://openapi.koreainvestment.com:9443"
        self.headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": api_key,
            "appsecret": api_secret,
            "tr_id": "FHKST03010200" # TR_ID for domestic stock intraday minute chart
        }

    def fetch_minute_data(self, ticker: str, interval_min: int = 3) -> pd.DataFrame:
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        
        # Grabs the most recent 30 entries from the current time
        params = {
            "FID_ETC_CLS_CODE": "",
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker,
            "FID_INPUT_HOUR_1": datetime.now().strftime("%H%M%00"),
            "FID_PW_DATA_INCU_YN": "N" # Exclude extended hours for clean swing signals
        }
        
        response = httpx.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        candles = response.json().get("output2", [])
        df = pd.DataFrame(candles)
        
        if df.empty:
            return df
            
        # Parse KIS date (YYYYMMDD) and hour (HHMMSS) strings
        df['datetime_str'] = df['stck_bsop_date'] + df['stck_cntg_hour']
        df['timestamp'] = pd.to_datetime(df['datetime_str'], format='%Y%m%d%H%M%S').dt.tz_localize('Asia/Seoul')
        
        df = df.rename(columns={
            'stck_oprc': 'open_price',
            'stck_hgpr': 'high_price',
            'stck_lwpr': 'low_price',
            'stck_prpr': 'close_price',
            'cntg_vol': 'volume',
            'acml_tr_pbmn': 'accumulated_value'
        })
        
        # Cast to correct types
        numeric_cols = ['open_price', 'high_price', 'low_price', 'close_price', 'volume', 'accumulated_value']
        df[numeric_cols] = df[numeric_cols].astype(float)
        
        df['ticker'] = ticker
        df['interval_min'] = interval_min
        
        return df[['ticker', 'interval_min', 'timestamp'] + numeric_cols]