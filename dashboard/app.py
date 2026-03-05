"""
Momentum-Ops Streamlit Dashboard — main entry point.

This file configures ``st.set_page_config``, renders the **shared sidebar**
(ticker selector + database status), and acts as the "Home" page.

Individual pages live in ``dashboard/pages/`` and are automatically
discovered by Streamlit's native multipage routing — no custom pills or
manual nav logic required.

Run with:
    streamlit run dashboard/app.py --server.port=8501
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import streamlit as st

# ── Ensure repo root is on sys.path so top-level packages resolve ─────────
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.config import settings  # noqa: E402
from shared.database import check_health  # noqa: E402

logger = logging.getLogger(__name__)

# ── Page config (must be the first Streamlit command) ─────────────────────
st.set_page_config(
    page_title="Momentum Ops — Market Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Minimal global CSS ────────────────────────────────────────────────────
st.markdown(
    "<style>.main { padding: 0rem 1rem; }</style>",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Shared Sidebar (rendered on every page via import)
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> str:
    """
    Render the sidebar controls shared by all pages.

    Returns the currently-selected ticker symbol and persists it in
    ``st.session_state["ticker"]``.
    """
    with st.sidebar:
        st.header("Configuration")

        # ── Ticker selection ──────────────────────────────────────────────
        ticker_list: list[str] = _load_ticker_list()
        default_ticker: str = settings.default_ticker

        if ticker_list:
            default_index = (
                ticker_list.index(default_ticker)
                if default_ticker in ticker_list
                else 0
            )
            ticker = st.selectbox(
                "Stock Ticker",
                options=ticker_list,
                index=default_index,
                help="Select an active ticker from the database",
            )
        else:
            ticker = st.text_input(
                "Stock Ticker",
                value=default_ticker,
                help="Enter a stock ticker symbol (e.g. AAPL, 005930.KS)",
            ).upper()

        st.session_state["ticker"] = ticker

        st.divider()

        # ── Database status indicator ─────────────────────────────────────
        st.subheader("Database Status")
        if check_health():
            st.success("Connected to database")
        else:
            st.error("Database connection failed")
            st.info(
                "Ensure PostgreSQL is running and credentials are set in "
                "the `.env` file or environment variables."
            )

        st.divider()

        # ── About ─────────────────────────────────────────────────────────
        st.subheader("About")
        st.info(
            "Momentum Ops provides real-time market analysis with technical "
            "indicators and XGBoost-based directional probability scores."
        )

    return ticker


@st.cache_data(ttl=300, show_spinner=False)
def _load_ticker_list() -> list[str]:
    """Fetch all ticker symbols from the database (cached 5 min)."""
    try:
        from shared.database import get_connection

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT symbol FROM tickers ORDER BY symbol")
                return [row["symbol"] for row in cur.fetchall()]
    except Exception:
        logger.warning("Could not load tickers from DB — falling back to empty list")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Home Page Content
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Render the Home page (landing page of the dashboard)."""
    ticker = render_sidebar()

    st.title("📈 Momentum Ops")
    st.markdown(
        f"Welcome to the Momentum Ops dashboard.  "
        f"Currently tracking **{ticker}**.  "
        f"Use the sidebar pages to explore directional outlook, momentum "
        f"analysis, AI-generated advisory prompts, or manage your tickers."
    )

    st.markdown("---")
    st.markdown(
        "### Quick Links\n"
        "| Page | Description |\n"
        "| --- | --- |\n"
        "| **Directional Outlook** | XGBoost probability scores across four strategy horizons |\n"
        "| **Momentum Analysis** | RSI, MACD, and Bollinger Band technical charts |\n"
        "| **AI Advisor** | Generate structured LLM prompts for secondary analysis |\n"
        "| **Manage Tickers** | Add, deactivate, or review tracked symbols |\n"
    )


if __name__ == "__main__":
    main()
