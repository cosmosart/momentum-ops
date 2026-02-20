"""
AI Advisor tab for the dashboard.
Generates a structured LLM prompt from the latest analysis data that the
user can copy-paste into ChatGPT / Gemini / Claude for secondary analysis.
"""

import streamlit as st
import json
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database
from dashboard.utils import format_price
from dashboard.prompt_generator import generate_llm_advisory_prompt

# ---------------------------------------------------------------------------
# Model display metadata (shared with predictions_tab — kept lightweight)
# ---------------------------------------------------------------------------
MODEL_META: dict[str, dict] = {
    "active_1w": {
        "label": "Active 1-Week",
        "icon": "⚡",
        "db_col": "prob_active_1w",
        "features_col": "features_active_1w",
    },
    "conservative_1mo": {
        "label": "Conservative 1-Month",
        "icon": "🛡️",
        "db_col": "prob_conservative_1mo",
        "features_col": "features_conservative_1mo",
    },
    "conservative_6mo": {
        "label": "Conservative 6-Month",
        "icon": "🛡️",
        "db_col": "prob_conservative_6mo",
        "features_col": "features_conservative_6mo",
    },
    "experimental": {
        "label": "Experimental (Next Business Day)",
        "icon": "🧪",
        "db_col": "prob_experimental",
        "features_col": "features_experimental",
    },
}

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

def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _fmt(val, d=4):
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.{d}f}"
    except (TypeError, ValueError):
        return "N/A"


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------

def render_ai_advisor_tab(ticker: str):
    """Render the AI Advisor export page."""
    import yfinance as yf

    try:
        ticker_obj = yf.Ticker(ticker)
        company_name = ticker_obj.info.get(
            "longName", ticker_obj.info.get("shortName", ticker)
        )
    except Exception:
        company_name = ticker

    st.header(f"Export for AI Advisor — {company_name}")
    st.caption(
        "Generate a structured prompt you can paste into ChatGPT, Gemini, "
        "or Claude for a secondary analysis with real-time web context."
    )

    # ------------------------------------------------------------------
    # Database fetch
    # ------------------------------------------------------------------
    db = Database()
    if not db.connect():
        st.error("Failed to connect to database")
        return

    try:
        analysis_data = db.get_analysis(ticker, limit=1)
        daily_prices = db.get_daily_prices(ticker, limit=30)

        if not daily_prices:
            st.warning(
                f"No data available for {ticker}. "
                "Data ingestion may still be in progress."
            )
            return

        df_prices = pd.DataFrame(daily_prices)
        df_prices["close"] = df_prices["close"].astype(float)
        current_price = df_prices.iloc[0]["close"]

        if not analysis_data:
            st.warning(
                "No analysis data available yet. "
                "The scheduler may not have run."
            )
            return

        analysis = analysis_data[0]

        # -- Summary metrics -----------------------------------------------
        st.metric("Current Price", format_price(current_price, ticker))
        st.caption(f"Analysis date: {analysis.get('date', 'N/A')}")
        st.divider()

        # -- Language selector ---------------------------------------------
        _lang_options = [
            "English", "Korean (한국어)", "Japanese (日本語)",
            "Chinese (中文)", "Spanish (Español)", "French (Français)",
            "German (Deutsch)", "Portuguese (Português)",
        ]
        response_language = st.selectbox(
            "Response Language",
            options=_lang_options,
            index=0,
            help="The LLM will respond in this language.",
        )
        # Strip parenthetical for the prompt instruction
        lang_clean = response_language.split(" (")[0]

        st.divider()

        # -- Generate button -----------------------------------------------
        if st.button("Generate AI Advisory Prompt", type="primary"):
            # Build quant_data_df
            quant_data_df = pd.DataFrame(
                {
                    "Indicator": [
                        "Ticker", "Date", "Current Price",
                        "RSI (14)", "MACD Line", "MACD Signal",
                        "MACD Histogram", "Bollinger Upper",
                        "Bollinger Middle", "Bollinger Lower",
                    ],
                    "Value": [
                        ticker,
                        str(analysis.get("date", "N/A")),
                        _fmt(current_price, 2),
                        _fmt(analysis.get("rsi"), 2),
                        _fmt(analysis.get("macd")),
                        _fmt(analysis.get("macd_signal")),
                        _fmt(analysis.get("macd_hist")),
                        _fmt(analysis.get("bb_upper"), 2),
                        _fmt(analysis.get("bb_middle"), 2),
                        _fmt(analysis.get("bb_lower"), 2),
                    ],
                }
            )

            # Build xgboost_results
            xgboost_results: dict[str, dict] = {}
            for mkey, minfo in MODEL_META.items():
                prob = _safe_float(analysis.get(minfo["db_col"]))

                raw_c = analysis.get(minfo["features_col"])
                contribs: dict | None = None
                if isinstance(raw_c, dict):
                    contribs = raw_c
                elif isinstance(raw_c, str):
                    try:
                        contribs = json.loads(raw_c)
                    except (json.JSONDecodeError, TypeError):
                        contribs = None

                shap_df = None
                if contribs:
                    rows_sorted = sorted(
                        contribs.items(),
                        key=lambda x: abs(x[1]),
                        reverse=True,
                    )
                    shap_df = pd.DataFrame(
                        [
                            {
                                "Feature": FEATURE_LABELS.get(f, f),
                                "SHAP Value": f"{v:+.4f}",
                                "Direction": "Up ↑" if v >= 0 else "Down ↓",
                            }
                            for f, v in rows_sorted
                        ]
                    )

                xgboost_results[mkey] = {
                    "label": f"{minfo['icon']} {minfo['label']}",
                    "prob": prob,
                    "shap_df": shap_df,
                }

            prompt_text = generate_llm_advisory_prompt(
                ticker=ticker,
                quant_data_df=quant_data_df,
                xgboost_results=xgboost_results,
                language=lang_clean,
            )
            st.code(prompt_text, language="markdown")

        # Disclaimer
        st.divider()
        st.caption(
            "⚠️ **Disclaimer:** The generated prompt is based on model-generated "
            "estimates and should be used for informational purposes only. "
            "Past performance does not guarantee future results. Not financial advice."
        )

    finally:
        db.close()
