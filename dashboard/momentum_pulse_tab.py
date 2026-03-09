"""
Momentum Pulse tab — real-time KIS-powered monitoring and analysis.

Provides all the charting functionality of the Momentum Core tab
(RSI, MACD, Bollinger Bands, moving averages, support/resistance, VWAP)
but sourced from the Korea Investment & Securities (KIS) REST API
instead of yfinance.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from dashboard.kis_client import KISDashboardClient, create_client
from dashboard.utils import format_price, get_currency_info
from models.models import calculate_indicators

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kr_format(value: int | float | None, suffix: str = "") -> str:
    """Format a Korean-market numeric value."""
    if value is None:
        return "N/A"
    return f"{value:,.0f}{suffix}"


def _investor_bar_chart(snapshot: dict) -> go.Figure:
    """Horizontal bar chart of investor-type net buying."""
    categories = ["Personal", "Foreign", "Institution"]
    values = [
        snapshot.get("personal_net_buy") or 0,
        snapshot.get("foreigner_net_buy") or 0,
        snapshot.get("institution_net_buy") or 0,
    ]
    colors = ["#4ECDC4" if v >= 0 else "#ef5350" for v in values]

    fig = go.Figure(go.Bar(
        x=values,
        y=categories,
        orientation="h",
        marker_color=colors,
        text=[f"{v:+,.0f}" for v in values],
        textposition="auto",
    ))
    fig.update_layout(
        title="Net Buy Qty by Investor Type",
        height=250,
        margin=dict(l=0, r=0, t=40, b=0),
        template="plotly_white",
        xaxis_title="Shares",
    )
    return fig


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def render_momentum_pulse_tab(ticker: str) -> None:
    """Render the Momentum Pulse tab for the given KR *ticker* (raw code)."""

    st.markdown(
        "<style>.block-container { max-width: 98%; padding-left: 1rem; "
        "padding-right: 1rem; }</style>",
        unsafe_allow_html=True,
    )

    region = st.session_state.get("ticker_region", "US")
    if region != "KR":
        st.warning(
            f"**{ticker}** is a **{region}** ticker.  "
            "Momentum Pulse uses the KIS API which only supports Korean (KR) equities.  \n"
            "Please select a KR ticker from the sidebar."
        )
        return

    # ── Initialise KIS client ─────────────────────────────────────────────
    try:
        client = _get_client()
    except RuntimeError as exc:
        st.error(f"KIS client error: {exc}")
        return

    st.header(f"Momentum Pulse — {ticker}")

    # ── Controls ──────────────────────────────────────────────────────────
    col_tf, col_period, col_ma_type, col_ma_select, col_bb, col_vwap, col_sr_toggle, col_sr_levels = st.columns(
        [1.2, 1.5, 1, 3, 1, 0.8, 1.5, 0.5]
    )

    with col_tf:
        timeframe = st.selectbox(
            "Timeframe",
            options=["5min", "10min", "15min", "30min", "60min", "240min", "Daily"],
            index=0,
            help="Intraday minute bars for the last trading session, or Daily bars.",
        )
        is_intraday = timeframe != "Daily"

    with col_period:
        if is_intraday:
            history_size = None  # minute endpoint returns a full day
            st.caption("Full session")
        else:
            history_size = st.selectbox(
                "History (bars)",
                options=[30, 50, 100, 150, 200],
                index=2,
                help="Number of daily bars to fetch from KIS",
            )

    with col_ma_type:
        ma_types = st.multiselect(
            "MA Type", options=["SMA", "EMA"], default=["EMA"],
            help="Simple or Exponential Moving Average",
        )

    with col_ma_select:
        ma_periods = st.multiselect(
            "Moving Averages",
            options=["5", "10", "20", "25", "50", "100", "200"],
            default=["5", "25"],
            help="MA periods to overlay on the price chart",
        )

    with col_bb:
        show_bollinger = st.checkbox("Bollinger Bands", value=False)

    with col_vwap:
        show_vwap = st.checkbox("VWAP", value=False)

    with col_sr_toggle:
        show_sr = st.checkbox("Support & Resistance", value=False)

    with col_sr_levels:
        sr_levels = st.selectbox("Levels", options=[1, 2, 3, 4, 5], index=0) if show_sr else 1

    # ── Fetch data ────────────────────────────────────────────────────────
    with st.spinner("Fetching data from KIS …"):
        try:
            quote = client.get_realtime_price(ticker)
            investor = client.get_investor_snapshot(ticker)
            if is_intraday:
                time_unit = timeframe.replace("min", "")
                df = client.get_minute_ohlcv(ticker, time_unit=time_unit)
            else:
                df = client.get_daily_ohlcv(ticker, period_code="D", count=history_size)
        except RuntimeError as exc:
            st.error(f"KIS API call failed: {exc}")
            return

    if df.empty:
        st.warning("No OHLCV history returned by KIS for this ticker.")
        return

    # ── Compute MAs ───────────────────────────────────────────────────────
    for ma_type in ma_types:
        for p in ma_periods:
            plen = int(p)
            col_name = f"{ma_type}{p}"
            if ma_type == "EMA":
                df[col_name] = df["Close"].ewm(span=plen, adjust=False).mean()
            else:
                df[col_name] = df["Close"].rolling(window=plen).mean()

    # ── Indicators (RSI / MACD) ───────────────────────────────────────────
    indicators = calculate_indicators(df)
    df = pd.concat([df, indicators], axis=1)

    # ── Metrics row ───────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 1.5, 1.5, 1.5])

    with c1:
        st.metric("Current Price", _kr_format(quote["current_price"], " KRW"))

    with c2:
        chg = quote.get("price_change")
        rate = quote.get("price_change_rate")
        if chg is not None and rate is not None:
            arrow = "▲" if chg >= 0 else "▼"
            color = "#09ab3b" if chg >= 0 else "#ff2b2b"
            st.markdown(
                f'<div style="font-size:0.875rem;color:rgba(49,51,63,0.6)">Day Change</div>'
                f'<div style="display:flex;align-items:baseline;gap:0.5rem">'
                f'<span style="font-size:1.75rem;font-weight:700">{rate:+.2f}%</span>'
                f'<span style="font-size:1rem;color:{color}">{arrow} {_kr_format(chg)} KRW</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.metric("Day Change", "N/A")

    with c3:
        # Trend from linear regression slope over available history
        if len(df) >= 3:
            closes = df["Close"].values.astype(float)
            x = np.arange(len(closes))
            slope, intercept = np.polyfit(x, closes, 1)
            fitted_start = intercept
            slope_pct = (slope / abs(fitted_start)) * 100 if fitted_start != 0 else 0.0
            trend_text = "📈 Uptrend" if slope_pct >= 0 else "📉 Downtrend"
            trend_color = "#09ab3b" if slope_pct >= 0 else "#ff2b2b"
            st.markdown(
                f'<div style="font-size:0.875rem;color:rgba(49,51,63,0.6)">Price Trend</div>'
                f'<div style="display:flex;align-items:baseline;gap:0.5rem">'
                f'<span style="font-size:1.85rem;font-weight:700;color:{trend_color}">{trend_text}</span>'
                f'<span style="font-size:1.75rem">{slope_pct:+.2f}%</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.metric("Price Trend", "N/A")

    with c4:
        if "RSI" in df.columns and not pd.isna(df.iloc[-1]["RSI"]):
            rsi_val = df.iloc[-1]["RSI"]
            if rsi_val > 70:
                sig, sig_c = "🔴 Overbought", "#ff2b2b"
            elif rsi_val < 30:
                sig, sig_c = "🟢 Oversold", "#09ab3b"
            else:
                sig, sig_c = "🟡 Neutral", "#faca2b"
            st.markdown(
                f'<div style="font-size:0.875rem;color:rgba(49,51,63,0.6)">RSI (14)</div>'
                f'<div style="display:flex;align-items:baseline;gap:0.5rem">'
                f'<span style="font-size:1.85rem;font-weight:700;color:{sig_c}">{sig}</span>'
                f'<span style="font-size:1.75rem">{rsi_val:.2f}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.metric("RSI (14)", "N/A")

    with c5:
        if "MACD" in df.columns and not pd.isna(df.iloc[-1]["MACD"]):
            macd_val = df.iloc[-1]["MACD"]
            sig_val = df.iloc[-1].get("MACD_signal")
            if sig_val is not None and not pd.isna(sig_val):
                if macd_val > sig_val:
                    sig, sig_c = "🟢 Bullish", "#09ab3b"
                else:
                    sig, sig_c = "🔴 Bearish", "#ff2b2b"
            else:
                sig, sig_c = "", "grey"
            st.markdown(
                f'<div style="font-size:0.875rem;color:rgba(49,51,63,0.6)">MACD</div>'
                f'<div style="display:flex;align-items:baseline;gap:0.5rem">'
                f'<span style="font-size:1.85rem;font-weight:700;color:{sig_c}">{sig}</span>'
                f'<span style="font-size:1.75rem;">{macd_val:.4f}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.metric("MACD", "N/A")

    st.divider()

    # ── Investor snapshot (collapsible) ───────────────────────────────────
    with st.expander("📊 Investor Trading Snapshot", expanded=False):
        icol1, icol2 = st.columns([1, 2])
        with icol1:
            st.markdown(f"**Data date:** {investor.get('data_date', 'N/A')}")
            inv_rows = {
                "Personal": investor.get("personal_net_buy"),
                "Foreign": investor.get("foreigner_net_buy"),
                "Institution": investor.get("institution_net_buy"),
            }
            for label, val in inv_rows.items():
                st.metric(f"{label} Net Buy", _kr_format(val))
        with icol2:
            st.plotly_chart(_investor_bar_chart(investor), use_container_width=True)

    # ── Build OHLCV chart ────────────────────────────────────────────────
    df = df.reset_index(drop=True)
    x_idx = df.index

    if is_intraday:
        tick_labels = df["Date"].dt.strftime("%H:%M")
    else:
        tick_labels = df["Date"].dt.strftime("%Y-%m-%d")
    n_ticks = min(len(df), 40)
    tick_step = max(1, len(df) // n_ticks)
    tick_vals = list(range(0, len(df), tick_step))
    tick_text = [tick_labels.iloc[i] for i in tick_vals]

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=("Price", "Volume", "RSI", "MACD"),
        row_heights=[1.0, 0.2, 0.2, 0.375],
        specs=[
            [{"secondary_y": False}],
            [{"secondary_y": True}],
            [{"secondary_y": False}],
            [{"secondary_y": False}],
        ],
    )

    # -- Candlestick -------------------------------------------------------
    fig.add_trace(
        go.Candlestick(
            x=x_idx,
            open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name="Price",
            customdata=tick_labels.values,
            hoverinfo="text",
            text=[
                f"{tick_labels.iloc[i]}<br>"
                f"O: {df['Open'].iloc[i]:,.0f}  H: {df['High'].iloc[i]:,.0f}<br>"
                f"L: {df['Low'].iloc[i]:,.0f}  C: {df['Close'].iloc[i]:,.0f}<br>"
                f"Vol: {int(df['Volume'].iloc[i]):,}"
                for i in range(len(df))
            ],
        ),
        row=1, col=1,
    )

    # -- Moving averages ---------------------------------------------------
    period_colors = {
        "5": "#FF6B6B", "10": "#FFA500", "20": "#4ECDC4", "25": "#FFD700",
        "50": "#95E1D3", "100": "#9B59B6", "200": "#3498DB",
    }
    line_styles = {"SMA": "solid", "EMA": "dash"}

    for ma_type in ma_types:
        for p in ma_periods:
            col_name = f"{ma_type}{p}"
            if col_name in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=x_idx, y=df[col_name], name=col_name,
                        customdata=tick_labels.values,
                        hovertemplate="%{customdata}<br>%{y:,.0f}<extra>%{fullData.name}</extra>",
                        line=dict(
                            color=period_colors.get(p, "#808080"),
                            width=1.5,
                            dash=line_styles.get(ma_type, "solid"),
                        ),
                        opacity=0.8,
                    ),
                    row=1, col=1,
                )

    # -- Bollinger Bands ---------------------------------------------------
    if show_bollinger:
        bb_mid = df["Close"].rolling(window=20).mean()
        bb_std = df["Close"].rolling(window=20).std()
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std

        fig.add_trace(go.Scatter(
            x=x_idx, y=bb_upper, name="BB Upper",
            line=dict(color="rgba(173,216,230,0.6)", width=1),
            customdata=tick_labels.values,
            hovertemplate="%{customdata}<br>BB Upper: %{y:,.0f}<extra></extra>",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=x_idx, y=bb_lower, name="BB Lower",
            line=dict(color="rgba(173,216,230,0.6)", width=1),
            fill="tonexty", fillcolor="rgba(173,216,230,0.12)",
            customdata=tick_labels.values,
            hovertemplate="%{customdata}<br>BB Lower: %{y:,.0f}<extra></extra>",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=x_idx, y=bb_mid, name="BB Mid",
            line=dict(color="rgba(173,216,230,0.8)", width=1, dash="dot"),
            customdata=tick_labels.values,
            hovertemplate="%{customdata}<br>BB Mid: %{y:,.0f}<extra></extra>",
        ), row=1, col=1)

    # -- Support & Resistance ----------------------------------------------
    if show_sr:
        support_levels, resistance_levels = _find_sr_levels(df, num_levels=sr_levels)
        for i, s in enumerate(support_levels, 1):
            fig.add_hline(
                y=s, line_dash="dot", line_color="green", line_width=2,
                opacity=max(0.7 - (i - 1) * 0.1, 0.3),
                annotation_text=f"S{i}: {s:,.0f} KRW",
                annotation_position="right", row=1, col=1,
            )
        for i, r in enumerate(resistance_levels, 1):
            fig.add_hline(
                y=r, line_dash="dot", line_color="red", line_width=2,
                opacity=max(0.7 - (i - 1) * 0.1, 0.3),
                annotation_text=f"R{i}: {r:,.0f} KRW",
                annotation_position="right", row=1, col=1,
            )

    # -- Volume ------------------------------------------------------------
    vol_colors = [
        "#26a69a" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "#ef5350"
        for i in range(len(df))
    ]
    fig.add_trace(
        go.Bar(
            x=x_idx, y=df["Volume"], name="Volume",
            marker_color=vol_colors, opacity=0.7, showlegend=False,
            customdata=tick_labels.values,
            hovertemplate="%{customdata}<br>Vol: %{y:,.0f}<extra></extra>",
        ),
        row=2, col=1,
    )

    vol_ma = df["Volume"].rolling(window=20).mean()
    fig.add_trace(
        go.Scatter(
            x=x_idx, y=vol_ma, name="Vol MA(20)",
            line=dict(color="#FFA500", width=1.5),
            customdata=tick_labels.values,
            hovertemplate="%{customdata}<br>Vol MA: %{y:,.0f}<extra></extra>",
        ),
        row=2, col=1,
    )

    # OBV on secondary y
    obv = [0]
    for i in range(1, len(df)):
        if df["Close"].iloc[i] > df["Close"].iloc[i - 1]:
            obv.append(obv[-1] + df["Volume"].iloc[i])
        elif df["Close"].iloc[i] < df["Close"].iloc[i - 1]:
            obv.append(obv[-1] - df["Volume"].iloc[i])
        else:
            obv.append(obv[-1])
    fig.add_trace(
        go.Scatter(
            x=x_idx, y=obv, name="OBV",
            line=dict(color="#9B59B6", width=1.2),
            customdata=tick_labels.values,
            hovertemplate="%{customdata}<br>OBV: %{y:,.0f}<extra></extra>",
        ),
        row=2, col=1, secondary_y=True,
    )
    fig.update_yaxes(title_text="OBV", showgrid=False, row=2, col=1, secondary_y=True)

    # -- VWAP on price chart -----------------------------------------------
    if show_vwap:
        cum_vol = df["Volume"].cumsum()
        cum_vwap = (df["Close"] * df["Volume"]).cumsum()
        vwap = cum_vwap / cum_vol
        fig.add_trace(
            go.Scatter(
                x=x_idx, y=vwap, name="VWAP",
                line=dict(color="#FF00FF", width=1.5, dash="dashdot"),
                customdata=tick_labels.values,
                hovertemplate="%{customdata}<br>VWAP: %{y:,.0f}<extra></extra>",
            ),
            row=1, col=1,
        )

    # -- RSI ---------------------------------------------------------------
    if "RSI" in df.columns:
        rsi_vals = df["RSI"]
        fig.add_trace(go.Scatter(
            x=x_idx, y=[70] * len(df), mode="lines",
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=x_idx, y=rsi_vals.where(rsi_vals >= 70), mode="lines",
            line=dict(width=0), showlegend=False, hoverinfo="skip",
            fill="tonexty", fillcolor="rgba(239,83,80,0.25)",
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=x_idx, y=[30] * len(df), mode="lines",
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=x_idx, y=rsi_vals.where(rsi_vals <= 30), mode="lines",
            line=dict(width=0), showlegend=False, hoverinfo="skip",
            fill="tonexty", fillcolor="rgba(38,166,154,0.25)",
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=x_idx, y=rsi_vals, name="RSI", line=dict(color="purple"),
            customdata=tick_labels.values,
            hovertemplate="%{customdata}<br>RSI: %{y:.2f}<extra></extra>",
        ), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)

    # -- MACD --------------------------------------------------------------
    if "MACD" in df.columns:
        fig.add_trace(go.Scatter(
            x=x_idx, y=df["MACD"], name="MACD", line=dict(color="blue"),
            customdata=tick_labels.values,
            hovertemplate="%{customdata}<br>MACD: %{y:.4f}<extra></extra>",
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=x_idx, y=df["MACD_signal"], name="Signal", line=dict(color="orange"),
            customdata=tick_labels.values,
            hovertemplate="%{customdata}<br>Signal: %{y:.4f}<extra></extra>",
        ), row=4, col=1)

        hist_vals = df["MACD_hist"].values
        hist_colors = []
        for i, v in enumerate(hist_vals):
            prev = hist_vals[i - 1] if i > 0 else 0
            diverging = abs(v) >= abs(prev)
            if v >= 0:
                hist_colors.append("#26a69a" if diverging else "#b2dfdb")
            else:
                hist_colors.append("#ef5350" if diverging else "#ef9a9a")
        fig.add_trace(go.Bar(
            x=x_idx, y=df["MACD_hist"], name="Histogram",
            marker_color=hist_colors,
            customdata=tick_labels.values,
            hovertemplate="%{customdata}<br>Hist: %{y:.4f}<extra></extra>",
        ), row=4, col=1)

    # -- Layout ------------------------------------------------------------
    fig.update_layout(
        height=1100, showlegend=True,
        xaxis_rangeslider_visible=False, hovermode="closest",
        spikedistance=-1,
    )
    for ax in ("xaxis", "xaxis2", "xaxis3", "xaxis4"):
        fig.update_layout(**{ax: dict(
            showspikes=True, spikemode="across", spikethickness=0.5,
            spikecolor="grey", spikedash="dot",
        )})

    fig.update_xaxes(tickvals=tick_vals, ticktext=tick_text, tickangle=-45, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)
    fig.update_xaxes(showticklabels=False, row=3, col=1)
    fig.update_xaxes(showticklabels=False, row=4, col=1)

    fig.update_yaxes(title_text="Price (KRW)", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", row=3, col=1)
    fig.update_yaxes(title_text="MACD", row=4, col=1)

    st.plotly_chart(fig, use_container_width=True)

    # ── Quote detail table ────────────────────────────────────────────────
    with st.expander("📋 Quote Details", expanded=False):
        detail_cols = st.columns(4)
        details = [
            ("Open", _kr_format(quote.get("open_price"))),
            ("High", _kr_format(quote.get("high_price"))),
            ("Low", _kr_format(quote.get("low_price"))),
            ("Prev Close", _kr_format(quote.get("prev_close"))),
            ("Volume", _kr_format(quote.get("total_volume"))),
            ("Trade Amount", _kr_format(quote.get("total_trade_amount"))),
            ("52w High", _kr_format(quote.get("high_52w"))),
            ("52w Low", _kr_format(quote.get("low_52w"))),
            ("Market Cap", _kr_format(quote.get("market_cap"))),
            ("PER", f"{quote['per']:.2f}" if quote.get("per") else "N/A"),
            ("PBR", f"{quote['pbr']:.2f}" if quote.get("pbr") else "N/A"),
            ("Checked At", quote.get("checked_at", "")),
        ]
        for idx, (label, val) in enumerate(details):
            with detail_cols[idx % 4]:
                st.metric(label, val)


# ---------------------------------------------------------------------------
# Support / Resistance helper (same logic as momentum_tab)
# ---------------------------------------------------------------------------

def _find_sr_levels(
    df: pd.DataFrame, num_levels: int = 3, window: int = 5,
) -> tuple[list[float], list[float]]:
    lows = df["Low"].values.astype(float)
    highs = df["High"].values.astype(float)

    support_candidates: list[float] = []
    for i in range(window, len(lows) - window):
        if all(lows[i] <= lows[i - window:i]) and all(lows[i] <= lows[i + 1:i + window + 1]):
            support_candidates.append(lows[i])
    support_candidates.append(float(df["Low"].min()))

    resistance_candidates: list[float] = []
    for i in range(window, len(highs) - window):
        if all(highs[i] >= highs[i - window:i]) and all(highs[i] >= highs[i + 1:i + window + 1]):
            resistance_candidates.append(highs[i])
    resistance_candidates.append(float(df["High"].max()))

    return (
        sorted(set(support_candidates))[:num_levels],
        sorted(set(resistance_candidates), reverse=True)[:num_levels],
    )


# ---------------------------------------------------------------------------
# Cached client
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _get_client() -> KISDashboardClient:
    return create_client()
