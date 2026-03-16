"""
KIS (Korea Investment & Securities) REST client for the Streamlit dashboard.
 
Provides real-time quote, investor-trading, and daily OHLCV data for
Korean domestic stocks via the KIS Open API.

Token handling:
    Reads the daily token from the JSON file at ``settings.kis_token_path``
    (written by the ``kis-token-renewal-flow`` Prefect flow).
    No automatic token issuance — reuse the existing daily token.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from shared.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def load_kis_token() -> str:
    """Read the current access token from the on-disk JSON file.

    Raises ``RuntimeError`` if the file is missing or has no ``access_token``.
    """
    token_path = Path(settings.kis_token_path)
    if not token_path.exists():
        raise RuntimeError(
            f"KIS token file not found at {token_path}. "
            "Run the kis-token-renewal-flow or set KIS_TOKEN_PATH."
        )

    data = json.loads(token_path.read_text())
    token = data.get("access_token")
    if not token:
        raise RuntimeError("KIS token file exists but contains no 'access_token' key.")
    return token


# ---------------------------------------------------------------------------
# Credentials dataclass
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class KISCredentials:
    app_key: str
    app_secret: str
    token: str | None = None
    base_url: str = field(default_factory=lambda: settings.kis_api_base_url)

    @classmethod
    def from_settings(cls) -> KISCredentials:
        app_key = settings.kis_app_key
        app_secret = settings.kis_app_secret
        if not app_key or not app_secret:
            raise RuntimeError("Missing KIS_APP_KEY or KIS_APP_SECRET in environment.")

        token = load_kis_token()
        return cls(
            app_key=app_key,
            app_secret=app_secret,
            token=token,
            base_url=settings.kis_api_base_url,
        )


# ---------------------------------------------------------------------------
# REST client
# ---------------------------------------------------------------------------

class KISDashboardClient:
    """Dashboard-oriented wrapper around KIS domestic stock endpoints."""

    def __init__(self, credentials: KISCredentials) -> None:
        self.credentials = credentials

    # -- low-level helpers -------------------------------------------------

    def _headers(self, tr_id: str) -> dict[str, str]:
        if not self.credentials.token:
            raise RuntimeError("No KIS access token available.")
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.credentials.token}",
            "appkey": self.credentials.app_key,
            "appsecret": self.credentials.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def _get(self, path: str, tr_id: str, params: dict[str, str]) -> dict:
        resp = requests.get(
            f"{self.credentials.base_url}{path}",
            headers=self._headers(tr_id),
            params=params,
            timeout=30,
        )
        payload = resp.json()
        if resp.status_code != 200 or payload.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS API error [{resp.status_code}] "
                f"{payload.get('msg_cd')}: {payload.get('msg1')}"
            )
        return payload

    @staticmethod
    def _int(value: str | int | None) -> int | None:
        if value in (None, ""):
            return None
        return int(str(value).replace(",", ""))

    # -- public data methods -----------------------------------------------

    def get_realtime_price(self, stock_code: str) -> dict[str, Any]:
        """Current price snapshot for one domestic stock."""
        out = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            "FHKST01010100",
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code},
        )["output"]
        return {
            "stock_code": stock_code,
            "current_price": self._int(out.get("stck_prpr")),
            "open_price": self._int(out.get("stck_oprc")),
            "high_price": self._int(out.get("stck_hgpr")),
            "low_price": self._int(out.get("stck_lwpr")),
            "total_volume": self._int(out.get("acml_vol")),
            "total_trade_amount": self._int(out.get("acml_tr_pbmn")),
            "price_change": self._int(out.get("prdy_vrss")),
            "price_change_rate": float(out["prdy_ctrt"]) if out.get("prdy_ctrt") else None,
            "prev_close": self._int(out.get("stck_sdpr")),
            "high_52w": self._int(out.get("stck_dryy_hgpr")),
            "low_52w": self._int(out.get("stck_dryy_lwpr")),
            "market_cap": self._int(out.get("hts_avls")),
            "per": float(out["per"]) if out.get("per") else None,
            "pbr": float(out["pbr"]) if out.get("pbr") else None,
            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_investor_snapshot(self, stock_code: str) -> dict[str, Any]:
        """Latest investor-type net-buy/sell quantities."""
        rows = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-investor",
            "FHKST01010900",
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code},
        )["output"]

        investor_fields = (
            "prsn_ntby_qty", "frgn_ntby_qty", "orgn_ntby_qty",
            "prsn_shnu_vol", "frgn_shnu_vol", "orgn_shnu_vol",
            "prsn_seln_vol", "frgn_seln_vol", "orgn_seln_vol",
        )
        latest = next(
            (r for r in rows if any(r.get(f) not in (None, "") for f in investor_fields)),
            rows[0] if rows else {},
        )
        return {
            "data_date": latest.get("stck_bsop_date"),
            "personal_net_buy": self._int(latest.get("prsn_ntby_qty")),
            "foreigner_net_buy": self._int(latest.get("frgn_ntby_qty")),
            "institution_net_buy": self._int(latest.get("orgn_ntby_qty")),
            "personal_buy_vol": self._int(latest.get("prsn_shnu_vol")),
            "foreigner_buy_vol": self._int(latest.get("frgn_shnu_vol")),
            "institution_buy_vol": self._int(latest.get("orgn_shnu_vol")),
            "personal_sell_vol": self._int(latest.get("prsn_seln_vol")),
            "foreigner_sell_vol": self._int(latest.get("frgn_seln_vol")),
            "institution_sell_vol": self._int(latest.get("orgn_seln_vol")),
        }

    def get_daily_ohlcv(
        self,
        stock_code: str,
        period_code: str = "D",
        count: int = 100,
    ) -> pd.DataFrame:
        """Fetch daily/weekly/monthly OHLCV history.

        ``period_code``: 'D' (daily), 'W' (weekly), 'M' (monthly).
        Returns a DataFrame sorted ascending by date.
        """
        today = datetime.now().strftime("%Y%m%d")
        out = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            "FHKST03010100",
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
                "FID_INPUT_DATE_1": "20200101",
                "FID_INPUT_DATE_2": today,
                "FID_PERIOD_DIV_CODE": period_code,
                "FID_ORG_ADJ_PRC": "0",
            },
        )["output2"]

        rows = []
        for r in out[:count]:
            rows.append({
                "Date": pd.Timestamp(r["stck_bsop_date"]),
                "Open": self._int(r.get("stck_oprc")),
                "High": self._int(r.get("stck_hgpr")),
                "Low": self._int(r.get("stck_lwpr")),
                "Close": self._int(r.get("stck_clpr")),
                "Volume": self._int(r.get("acml_vol")),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("Date").reset_index(drop=True)
        return df

    def get_minute_ohlcv(
        self,
        stock_code: str,
        time_unit: str = "1",  # Default to 1 for maximum granularity
    ) -> pd.DataFrame:
        """Fetch intraday minute-bar OHLCV for the current/last trading day."""
        rows: list[dict] = []
        # KIS expects HHMMSS. 16:00:00 covers the full day including after-hours adjustment
        hour_cursor = "160000"
        
        # We use a safety break to prevent infinite loops
        for _ in range(40): 
            payload = self._get(
                "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
                "FHKST03010200",
                {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": stock_code,
                    "FID_ETC_CLS_CODE": time_unit,
                    "FID_INPUT_HOUR_1": hour_cursor,
                    "FID_PW_DATA_INCU_YN": "Y", # Changed to Y to include previous day if today is empty
                },
            )
            output2 = payload.get("output2", [])
            if not output2:
                break

            for r in output2:
                hhmm = r.get("stck_cntg_hour", "")
                bsop_date = r.get("stck_bsop_date", "")
                if not hhmm or not bsop_date:
                    continue
                
                rows.append({
                    "Date": bsop_date,
                    "Time": hhmm,
                    "Open": self._int(r.get("stck_oprc")),
                    "High": self._int(r.get("stck_hgpr")),
                    "Low": self._int(r.get("stck_lwpr")),
                    "Close": self._int(r.get("stck_prpr")),
                    "Volume": self._int(r.get("cntg_vol")),
                })

            # Get the earliest time in this batch to move the cursor back
            earliest_time = output2[-1].get("stck_cntg_hour", "")
            
            # STOP CONDITIONS:
            # 1. We reached the market open
            if earliest_time <= "090000":
                break
            # 2. The cursor didn't move (no more data)
            if earliest_time == hour_cursor:
                break
                
            hour_cursor = earliest_time

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # Clean duplicates (paging often overlaps the last/first row)
        df = df.drop_duplicates(subset=["Date", "Time"], keep="first")
        
        # Convert to Datetime
        df["Datetime"] = pd.to_datetime(
            df["Date"] + df["Time"], format="%Y%m%d%H%M%S", errors="coerce"
        )
        df = df.dropna(subset=["Datetime"])

        # FIX: Instead of complex filtering against 'now', we only filter 
        # out bars that are truly impossible (e.g., tomorrow).
        # We trust KIS's bsop_date for the 'current' day.
        latest_date = df["Date"].max()
        df = df[df["Date"] == latest_date]
        
        # Sort to ascending order
        df = df.sort_values("Datetime").reset_index(drop=True)
        
        return df

    def collect_realtime_ticks(
        self,
        stock_code: str,
        interval_seconds: int = 2,
        iterations: int = 20,
    ) -> pd.DataFrame:
        """Poll the quote endpoint and return raw tick rows."""
        rows: list[dict] = []
        for i in range(iterations):
            rows.append(self.get_realtime_price(stock_code))
            if i < iterations - 1:
                time.sleep(interval_seconds)
        return pd.DataFrame(rows)

    @staticmethod
    def build_realtime_candles(
        ticks_df: pd.DataFrame,
        candle_seconds: int = 10,
    ) -> pd.DataFrame:
        """Aggregate polled ticks into OHLCV candles."""
        if ticks_df.empty:
            return pd.DataFrame(
                columns=["candle_time", "open", "high", "low", "close", "interval_volume"]
            )
        df = ticks_df.copy()
        df["checked_at"] = pd.to_datetime(df["checked_at"])
        df = df.sort_values("checked_at")
        df["tick_volume"] = df["total_volume"].diff().fillna(0).clip(lower=0)

        return (
            df.set_index("checked_at")
            .resample(f"{candle_seconds}s")
            .agg(
                open=("current_price", "first"),
                high=("current_price", "max"),
                low=("current_price", "min"),
                close=("current_price", "last"),
                interval_volume=("tick_volume", "sum"),
            )
            .dropna(subset=["open", "high", "low", "close"])
            .reset_index()
            .rename(columns={"checked_at": "candle_time"})
        )


def create_client() -> KISDashboardClient:
    """Factory: build a client from shared Settings + on-disk token."""
    return KISDashboardClient(KISCredentials.from_settings())
