"""
Momentum Pulse tab — real-time KIS-powered monitoring and analysis.

Provides all the charting functionality of the Momentum Core tab
sourced from the Korea Investment & Securities (KIS) REST API
and local high-frequency database, fixed for 15:30 KST close.
"""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from dashboard.kis_client import KISDashboardClient, create_client
from models.models import calculate_indicators

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kr_format(value: int | float | None, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.0f}{suffix}"

def _investor_bar_chart(snapshot: dict) -> go.Figure:
    categories = ["Personal", "Foreign", "Institution"]
    values = [
        snapshot.get("personal_net_buy") or 0,
        snapshot.get("foreigner_net_buy") or 0,
        snapshot.get("institution_net_buy") or 0,
    ]
    colors = ["#4ECDC4" if v >= 0 else "#ef5350" for v in values]
    fig = go.Figure(go.Bar(
        x=values, y=categories, orientation="h",
        marker_color=colors, text=[f"{v:+,.0f}" for v in values],
        textposition="auto",
    ))
    fig.update_layout(
        title="Net Buy Qty by Investor Type", height=250,
        margin=dict(l=0, r=0, t=40, b=0), template="plotly_white",
    )
    return fig

# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def render_momentum_pulse_tab(ticker: str) -> None:
    st.markdown(
        "<style>.block-container { max-width: 98%; padding-left: 1rem; padding-right: 1rem; }</style>",
        unsafe_allow_html=True,
    )

    region = st.session_state.get("ticker_region", "US")
    if region != "KR":
        st.warning(f"Momentum Pulse requires a KR ticker. Current: {region}")
        return

    try:
        client = _get_client()
    except RuntimeError as exc:
        st.error(f"KIS client error: {exc}")
        return

    st.header(f"Momentum Pulse — {ticker}")

    # ── Controls ──────────────────────────────────────────────────────────
    col_at, col_tf, col_period, col_ma_type, col_ma_select, col_bb, col_vwap, col_sr_toggle = st.columns(
        [1.2, 1.2, 1.2, 1, 2.5, 0.8, 0.7, 1.2]
    )

    with col_at:
        analysis_type = st.selectbox("Analysis Type", ["Daily", "2 Days", "5 Days", "7 Days", "Custom period"])
    with col_tf:
        timeframe = st.selectbox("Timeframe", ["1min", "3min", "5min", "10min", "15min", "30min", "60min"])
    with col_period:
        _analysis_day_map = {"Daily": 1, "2 Days": 2, "5 Days": 5, "7 Days": 7}
        history_days = st.number_input("Days", 1, 30, 3) if analysis_type == "Custom period" else _analysis_day_map.get(analysis_type, 1)
    with col_ma_type:
        ma_types = st.multiselect("MA", ["SMA", "EMA"], ["EMA"])
    with col_ma_select:
        ma_periods = st.multiselect("Periods", ["5", "10", "20", "25", "50", "100", "200"], ["5", "25"])
    with col_bb:
        show_bollinger = st.checkbox("BB", False)
    with col_vwap:
        show_vwap = st.checkbox("VWAP", False)
    with col_sr_toggle:
        show_sr = st.checkbox("S/R", False)

    # ── Data Acquisition Logic ───────────────────────────────────────────
    time_unit = timeframe.replace("min", "")
    interval_val = int(time_unit)

    # 1. Fetch Snapshot
    with st.spinner("Fetching KIS Snapshot..."):
        quote = client.get_realtime_price(ticker)
        investor = client.get_investor_snapshot(ticker)

    # 2. Fetch Today's Real-time Data (Fixes the 13:35 DB gap)
    with st.spinner("Syncing Live KIS Bars..."):
        try:
            df_today = client.get_minute_ohlcv(ticker, time_unit="1") # Always get 1m for resampling
            if not df_today.empty:
                # Localize to Seoul and strip TZ for clean merge
                df_today["Datetime"] = df_today["Datetime"].dt.tz_localize(None)
        except Exception:
            df_today = pd.DataFrame()

    # 3. Fetch Historical Data from Local DB (Fixes the 7-day seed)
    df_hist = pd.DataFrame()
    if history_days >= 1:
        from database.db import Database
        import pandas.io.sql as psql
        db = Database()
        if db.connect():
            query = """
                SELECT timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul' as "Datetime", 
                       open_price as "Open", high_price as "High", low_price as "Low", 
                       close_price as "Close", volume as "Volume"
                FROM kr_minute_ohlcv
                WHERE ticker = %(ticker)s AND interval_min = 1
                  AND timestamp >= (NOW() AT TIME ZONE 'Asia/Seoul' - CAST(%(lookback)s AS INTERVAL))
                ORDER BY timestamp ASC
            """
            df_hist = psql.read_sql(query, db.conn, params={"ticker": ticker, "lookback": f"{history_days + 2} days"})
            db.close()
            if not df_hist.empty:
                df_hist["Datetime"] = pd.to_datetime(df_hist["Datetime"]).dt.tz_localize(None)

    # 4. Merge and Resample
    df_raw = pd.concat([df_hist, df_today], ignore_index=True)
    if df_raw.empty:
        st.error("No data available.")
        return

    # Drop duplicates (KIS live data overwrites DB rows)
    df_raw = df_raw.sort_values("Datetime").drop_duplicates(subset=["Datetime"], keep="last")

    # Dynamic Resampling to User timeframe
    df = df_raw.set_index("Datetime").resample(f"{interval_val}min").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
    }).dropna().reset_index()

    # Trim to history_days
    unique_dates = sorted(df["Datetime"].dt.date.unique())
    if len(unique_dates) > history_days:
        df = df[df["Datetime"].dt.date.isin(unique_dates[-history_days:])]

    # ── Indicators ──────────────────────────────────────────────────────
    for mt in ma_types:
        for p in ma_periods:
            if mt == "EMA": df[f"{mt}{p}"] = df["Close"].ewm(span=int(p), adjust=False).mean()
            else: df[f"{mt}{p}"] = df["Close"].rolling(window=int(p)).mean()

    indicators = calculate_indicators(df)
    df = pd.concat([df, indicators], axis=1)
    
    # VWAP & OBV
    df["VWAP"] = (df["Close"] * df["Volume"]).cumsum() / df["Volume"].cumsum()
    obv_change = np.where(df["Close"] > df["Close"].shift(1), df["Volume"], 
                          np.where(df["Close"] < df["Close"].shift(1), -df["Volume"], 0))
    df["OBV"] = obv_change.cumsum()
    df["OBV_signal"] = df["OBV"].ewm(span=20, adjust=False).mean()

    # ── Rendering ───────────────────────────────────────────────────────
    # (Metrics Row)
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Price", _kr_format(quote.get("current_price"), " KRW"))
    with m2: st.metric("RSI (14)", f"{df.iloc[-1]['RSI']:.1f}" if "RSI" in df.columns else "N/A")
    with m3: st.metric("MACD", f"{df.iloc[-1]['MACD']:.2f}" if "MACD" in df.columns else "N/A")
    with m4: st.metric("VWAP", _kr_format(df.iloc[-1]['VWAP']))

    # (Chart Building)
    df = df.reset_index(drop=True)
    tick_labels = df["Datetime"].dt.strftime("%H:%M" if history_days == 1 else "%m/%d %H:%M")
    
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.5, 0.1, 0.15, 0.25], specs=[[{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": False}], [{"secondary_y": False}]])

    # Price & Candlestick
    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"], name="Price"), row=1, col=1)
    
    # MAs
    for mt in ma_types:
        for p in ma_periods:
            fig.add_trace(go.Scatter(x=df.index, y=df[f"{mt}{p}"], name=f"{mt}{p}", line=dict(width=1.2)), row=1, col=1)

    # Volume & OBV
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Volume", marker_color="gray", opacity=0.5), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["OBV"], name="OBV", line=dict(color="purple")), row=2, col=1, secondary_y=True)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="blue")), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    # MACD
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD"), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal"), row=4, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], name="Hist"), row=4, col=1)

    fig.update_layout(height=900, template="plotly_white", xaxis_rangeslider_visible=False)
    fig.update_xaxes(tickvals=list(range(0, len(df), max(1, len(df)//20))), ticktext=tick_labels[::max(1, len(df)//20)])

    st.plotly_chart(fig, use_container_width=True)

    # Expander Details
    with st.expander("Investor & Quote Details"):
        st.plotly_chart(_investor_bar_chart(investor))
        st.write(quote)

@st.cache_resource(show_spinner=False)
def _get_client() -> KISDashboardClient:
    return create_client()