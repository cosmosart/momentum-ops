"""
Predictions tab for the dashboard.
Displays directional probabilities from four targeted XGBoost models and the
technical features that contributed to the latest prediction.

Four models loaded in a single container:
  1. Active 1-Week        — high-risk short-term momentum
  2. Conservative 1-Month — foundational mid-term
  3. Conservative 6-Month — foundational long-term
  4. Experimental         — next-business-day directional prediction
"""

import streamlit as st
import json
import pandas as pd
import plotly.graph_objects as go
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database
from dashboard.utils import format_price, get_currency_info

# ---------------------------------------------------------------------------
# Model display metadata — exactly four entries
# ---------------------------------------------------------------------------
MODEL_META: dict[str, dict] = {
    "active_1w": {
        "label": "Active 1-Week",
        "icon": "⚡",
        "description": "High-risk short-term momentum trades",
        "db_col": "prob_active_1w",
        "features_col": "features_active_1w",
    },
    "conservative_1mo": {
        "label": "Conservative 1-Month",
        "icon": "🛡️",
        "description": "Foundational mid-term holds",
        "db_col": "prob_conservative_1mo",
        "features_col": "features_conservative_1mo",
    },
    "conservative_6mo": {
        "label": "Conservative 6-Month",
        "icon": "🛡️",
        "description": "Foundational long-term holds",
        "db_col": "prob_conservative_6mo",
        "features_col": "features_conservative_6mo",
    },
    "experimental": {
        "label": "Experimental (Next Business Day)",
        "icon": "🧪",
        "description": "Next-business-day directional prediction — 1 trading day horizon",
        "db_col": "prob_experimental",
        "features_col": "features_experimental",
    },
}

# Human-readable labels for engineered feature column names
FEATURE_LABELS: dict[str, str] = {
    "rsi_14": "RSI (14)",
    "macd_line": "MACD Line",
    "macd_signal": "MACD Signal",
    "macd_hist": "MACD Histogram",
    "bb_upper": "Bollinger Upper",
    "bb_middle": "Bollinger Middle",
    "bb_lower": "Bollinger Lower",
    "bb_pctb": "Bollinger %B",
    "logret_1": "1-Day Log Return",
    "logret_2": "2-Day Log Return",
    "logret_3": "3-Day Log Return",
    "logret_5": "5-Day Log Return",
    "logret_10": "10-Day Log Return",
    "atr_14": "ATR (14)",
    "rolling_vol_20": "Rolling Volatility (20)",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def fetch_prediction_data(ticker: str) -> tuple[list | None, list | None]:
    """
    Fetch prediction and price data from the database. 
    Cached for 5 minutes to prevent redundant queries on UI interactions.
    """
    db = Database()
    if not db.connect():
        return None, None
        
    try:
        analysis = db.get_analysis(ticker, limit=1)
        prices = db.get_daily_prices(ticker, limit=30)
        return analysis, prices
    finally:
        db.close()


def _classify_regime(prob: float) -> tuple[str, str, str]:
    """
    Map a directional probability to a human-readable regime label.
    Returns (label, colour, emoji).
    """
    if prob >= 0.70:
        return "Strong Bullish", "#00c853", "🟢"
    elif prob >= 0.55:
        return "Bullish", "#66bb6a", "🟩"
    elif prob >= 0.45:
        return "Neutral", "#ffa726", "🟨"
    else:
        return "Bearish", "#ef5350", "🟥"


def _build_gauge(prob: float, label: str, colour: str, horizon_label: str) -> go.Figure:
    """
    Create a Plotly gauge (indicator) for the directional probability.
    """
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=prob * 100,
            number={"suffix": "%", "font": {"size": 48}},
            title={
                "text": f"{horizon_label} Directional Probability — {label}",
                "font": {"size": 20},
            },
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 2},
                "bar": {"color": colour, "thickness": 0.6},
                "bgcolor": "white",
                "steps": [
                    {"range": [0, 45], "color": "#ffcdd2"},
                    {"range": [45, 55], "color": "#fff9c4"},
                    {"range": [55, 70], "color": "#c8e6c9"},
                    {"range": [70, 100], "color": "#a5d6a7"},
                ],
                "threshold": {
                    "line": {"color": "black", "width": 3},
                    "thickness": 0.8,
                    "value": prob * 100,
                },
            },
        )
    )
    fig.update_layout(height=320, margin=dict(t=60, b=20, l=40, r=40))
    return fig


def _build_mini_gauge(prob: float, label: str, colour: str) -> go.Figure:
    """
    Compact gauge for the summary row (shown when "All" horizons selected).
    """
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=prob * 100,
            number={"suffix": "%", "font": {"size": 28}},
            title={"text": label, "font": {"size": 14}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": colour, "thickness": 0.6},
                "bgcolor": "white",
                "steps": [
                    {"range": [0, 45], "color": "#ffcdd2"},
                    {"range": [45, 55], "color": "#fff9c4"},
                    {"range": [55, 70], "color": "#c8e6c9"},
                    {"range": [70, 100], "color": "#a5d6a7"},
                ],
            },
        )
    )
    fig.update_layout(height=200, margin=dict(t=40, b=10, l=20, r=20))
    return fig


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def render_predictions_tab(ticker: str):
    """
    Render the predictions tab with strategy and horizon selectors.

    Args:
        ticker: Raw stock ticker symbol (no yfinance suffix)
    """
    yf_symbol = st.session_state.get("yf_symbol", ticker)
    region = st.session_state.get("ticker_region", "US")

    # Get company name
    import yfinance as yf
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        company_name = ticker_obj.info.get("longName", ticker_obj.info.get("shortName", ticker))
    except Exception:
        company_name = ticker

    st.header(f"Directional Outlook for {company_name}")

    # ------------------------------------------------------------------
    # Database fetch (Cached)
    # ------------------------------------------------------------------
    analysis_data, daily_prices = fetch_prediction_data(ticker)

    if analysis_data is None and daily_prices is None:
        st.error("Failed to connect to database or retrieve data.")
        return

    if not daily_prices:
        st.warning(f"No data available for {ticker}. Data ingestion may still be in progress.")
        st.info("Please wait for the Prefect ingestion flow to complete, or trigger a run manually.")
        return

    # Extract Current Price safely by explicitly sorting dates
    df_prices = pd.DataFrame(daily_prices)
    if "date" in df_prices.columns:
        df_prices["date"] = pd.to_datetime(df_prices["date"])
        df_prices = df_prices.sort_values("date", ascending=False)
        
    df_prices["close"] = df_prices["close"].astype(float)
    current_price = float(df_prices.iloc[0]["close"])

    st.metric("Current Price", format_price(current_price, yf_symbol))

    # ------------------------------------------------------------------
    # Model selector — Contextually aware defaults based on strategic mandates
    # ------------------------------------------------------------------
    if region == "KR":
        default_key = "active_1w"
    elif region == "JP":
        default_key = "conservative_6mo"
    else:
        default_key = "conservative_1mo"

    model_keys = list(MODEL_META.keys())
    model_labels = [
        f"{MODEL_META[k]['icon']} {MODEL_META[k]['label']}"
        for k in model_keys
    ]

    default_idx = model_keys.index(default_key) if default_key in model_keys else 0

    selected_model_label = st.pills(
        "Model Focus",
        options=model_labels,
        default=model_labels[default_idx],
        label_visibility="collapsed",
    )
    
    # Handle the case where the user deselects all pills
    if selected_model_label is None:
        selected_model_label = model_labels[default_idx]
        
    selected_model = model_keys[model_labels.index(selected_model_label)]
    mmeta = MODEL_META[selected_model]

    # ------------------------------------------------------------------
    # Directional probability gauge — for the selected model
    # ------------------------------------------------------------------
    st.subheader("Market Regime")

    if analysis_data:
        analysis = analysis_data[0]

        def _safe_float(val):
            if val is None:
                return None
            try:
                return float(val)
            except (TypeError, ValueError):
                return None

        raw_prob = _safe_float(analysis.get(mmeta["db_col"]))

        if raw_prob is not None:
            prob = raw_prob
            label, colour, emoji = _classify_regime(prob)

            gauge_fig = _build_gauge(prob, label, colour, mmeta["label"])
            st.plotly_chart(gauge_fig, use_container_width=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Probability", f"{prob * 100:.1f}%")
            with col2:
                st.metric("Regime", f"{emoji} {label}")
            with col3:
                analysis_date = analysis.get("date", "N/A")
                st.metric("As Of", str(analysis_date))
        else:
            st.warning(
                f"No probability available for **{mmeta['label']}**. "
                "The model may not be deployed yet or the ingestion flow hasn't run."
            )

        st.divider()

        # ------------------------------------------------------------------
        # Contributing technical features (per-model local SHAP)
        # ------------------------------------------------------------------
        st.subheader("Contributing Features")
        st.caption(
            "Top drivers for this model's latest prediction — "
            "computed via TreeSHAP (local explainability). "
            "Green = pushes toward Up · Red = pushes toward Down."
        )

        features_col = mmeta["features_col"]
        raw_contribs = analysis.get(features_col)

        # Parse JSONB — psycopg may return a dict or a JSON string
        contribs_dict: dict | None = None
        if raw_contribs is not None:
            if isinstance(raw_contribs, dict):
                contribs_dict = raw_contribs
            elif isinstance(raw_contribs, str):
                try:
                    contribs_dict = json.loads(raw_contribs)
                except (json.JSONDecodeError, TypeError):
                    contribs_dict = None

        if contribs_dict:
            # Sort by absolute impact (descending) for visual hierarchy
            sorted_features = sorted(
                contribs_dict.items(), key=lambda x: abs(x[1]), reverse=True
            )
            labels = [
                FEATURE_LABELS.get(name, name) for name, _ in sorted_features
            ]
            values = [val for _, val in sorted_features]
            colors = ["#4caf50" if v >= 0 else "#ef5350" for v in values]

            fig_shap = go.Figure(
                go.Bar(
                    x=values,
                    y=labels,
                    orientation="h",
                    marker_color=colors,
                    text=[f"{v:+.4f}" for v in values],
                    textposition="outside",
                )
            )
            fig_shap.update_layout(
                title=f"SHAP Contributions — {mmeta['icon']} {mmeta['label']}",
                xaxis_title="SHAP Value (impact on prediction)",
                yaxis_title="",
                height=220,
                margin=dict(t=40, b=30, l=140, r=60),
                yaxis=dict(autorange="reversed"),
                showlegend=False,
            )
            st.plotly_chart(fig_shap, use_container_width=True)
        else:
            st.info(
                "Feature contributions not yet available for this model. "
                "They will appear after the next Prefect flow run."
            )

        st.divider()

        # ------------------------------------------------------------------
        # Current signal values
        # ------------------------------------------------------------------
        st.subheader("Current Signal Values")
        st.caption("Latest indicator snapshots stored by the ingestion flow.")

        rsi = _safe_float(analysis.get("rsi"))
        macd_val = _safe_float(analysis.get("macd"))
        macd_sig = _safe_float(analysis.get("macd_signal"))
        macd_h = _safe_float(analysis.get("macd_hist"))
        bb_up = _safe_float(analysis.get("bb_upper"))
        bb_mid = _safe_float(analysis.get("bb_middle"))
        bb_lo = _safe_float(analysis.get("bb_lower"))

        # Row 1 — RSI + MACD
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if rsi is not None:
                st.metric("RSI (14)", f"{rsi:.2f}")
                if rsi > 70:
                    st.caption("⚠️ Overbought")
                elif rsi < 30:
                    st.caption("⚠️ Oversold")
            else:
                st.metric("RSI (14)", "N/A")
        with c2:
            if macd_val is not None:
                st.metric("MACD", f"{macd_val:.4f}")
            else:
                st.metric("MACD", "N/A")
        with c3:
            if macd_sig is not None:
                st.metric("MACD Signal", f"{macd_sig:.4f}")
            else:
                st.metric("MACD Signal", "N/A")
        with c4:
            if macd_h is not None:
                st.metric("MACD Hist", f"{macd_h:.4f}")
            else:
                st.metric("MACD Hist", "N/A")

        # Row 2 — Bollinger Bands
        b1, b2, b3, b4 = st.columns(4)
        with b1:
            if bb_up is not None:
                st.metric("Bollinger Bands Upper", format_price(bb_up, yf_symbol))
            else:
                st.metric("Bollinger Bands Upper", "N/A")
        with b2:
            if bb_mid is not None:
                st.metric("Bollinger Bands Middle", format_price(bb_mid, yf_symbol))
            else:
                st.metric("Bollinger Bands Middle", "N/A")
        with b3:
            if bb_lo is not None:
                st.metric("Bollinger Bands Lower", format_price(bb_lo, yf_symbol))
            else:
                st.metric("Bollinger Bands Lower", "N/A")
        with b4:
            if bb_up is not None and bb_lo is not None and bb_up != bb_lo:
                pctb = (current_price - bb_lo) / (bb_up - bb_lo)
                st.metric("Bollinger Bands %B", f"{pctb:.2f}")
            else:
                st.metric("Bollinger Bands %B", "N/A")

        st.divider()

        # ------------------------------------------------------------------
        # All-models comparison (always visible)
        # ------------------------------------------------------------------
        st.subheader("All Models Overview")

        available = []
        for mkey, minfo in MODEL_META.items():
            prob = _safe_float(analysis.get(minfo["db_col"]))
            if prob is not None:
                available.append((mkey, minfo, prob))

        if available:
            cols = st.columns(len(available))
            for col_widget, (mkey, minfo, prob) in zip(cols, available):
                label, colour, emoji = _classify_regime(prob)
                with col_widget:
                    mini_fig = _build_mini_gauge(
                        prob, f"{minfo['icon']} {minfo['label']}", colour
                    )
                    st.plotly_chart(mini_fig, use_container_width=True)
                    st.caption(f"{emoji} {label}")
        else:
            st.warning(
                "No strategy model probabilities available yet. "
                "Make sure XGBoost models are deployed and the ingestion flow has run."
            )

        st.divider()

        # ------------------------------------------------------------------
        # Regime interpretation
        # ------------------------------------------------------------------
        st.subheader("Signal Interpretation")

        with st.expander("ℹ️  How to read the gauge", expanded=False):
            st.markdown("""
This prediction uses **XGBoost classifiers** trained on RSI, MACD,
Bollinger Bands, ATR, rolling volatility, and lagged returns to estimate
the probability that the closing price will be **higher** over the model's
target horizon. Four targeted models run in a single container.

| Range | Regime | Meaning |
|-------|--------|---------|
| **> 70%** | 🟢 Strong Bullish | Model is confident price will be higher over the target horizon |
| **55–70%** | 🟩 Bullish | Moderate upward bias detected |
| **45–55%** | 🟨 Neutral | No clear directional edge (coin-flip territory) |
| **< 45%** | 🟥 Bearish | Model leans toward a price decline |

**Four targeted models:**
| Model | Description |
|-------|-------------|
| ⚡ Active 1-Week | High-risk short-term momentum — 5 trading days |
| 🛡️ Conservative 1-Month | Foundational mid-term holds — 21 trading days |
| 🛡️ Conservative 6-Month | Foundational long-term holds — 126 trading days |
| 🧪 Experimental (Next Business Day) | Next-business-day directional prediction — 1 trading day, 0.5% hurdle |

All four models share the **same feature engineering pass** (RSI, MACD,
Bollinger Bands, ATR, rolling volatility, lagged log-returns) run once per
ticker per cycle.  Each model applies different training parameters / hurdle
rates.

The "Contributing Features" bar chart shows **local** (per-prediction)
TreeSHAP values — not global feature importance.  Green bars push the
probability toward "Up", red bars push it toward "Down/Flat".
            """)

    else:
        st.warning("No analysis data available yet. Data ingestion may still be in progress.")

    # Disclaimer
    st.divider()
    st.caption(
        "⚠️ **Disclaimer:** Directional probabilities are model-generated estimates "
        "and should be used for informational purposes only. "
        "Past performance does not guarantee future results. Not financial advice."
    )