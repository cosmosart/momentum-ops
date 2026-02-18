"""
Streamlit dashboard application for momentum-ops.
Main entry point for the dashboard.
"""

import os
import sys
import streamlit as st
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database
from dashboard.momentum_tab import render_momentum_tab
from dashboard.predictions_tab import render_predictions_tab

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Momentum Ops - Market Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)


def main():
    """Main dashboard application."""
    
    # Title
    st.title("📈 Momentum Ops - Market Analysis Dashboard")
    
    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        
        # Ticker selection
        ticker = st.text_input(
            "Stock Ticker",
            value=os.getenv('DEFAULT_TICKER', 'AAPL'),
            help="Enter a stock ticker symbol (e.g., AAPL, GOOGL, MSFT)"
        ).upper()
        
        st.divider()
        
        # Database connection status
        st.subheader("Database Status")
        db = Database()
        if db.connect():
            st.success("✅ Connected to database")
            db.close()
        else:
            st.error("❌ Database connection failed")
            st.info("Make sure PostgreSQL is running and credentials are correct in .env file")
        
        st.divider()
        
        # Information
        st.subheader("About")
        st.info(
            "Momentum Ops provides real-time market analysis with technical indicators "
            "and price predictions for stocks."
        )
    
    # Main content area with tabs
    tab1, tab2 = st.tabs(["📊 Momentum Analysis", "🔮 Predictions"])
    
    with tab1:
        render_momentum_tab(ticker)
    
    with tab2:
        render_predictions_tab(ticker)


if __name__ == "__main__":
    main()
