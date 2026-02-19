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
from dashboard.ticker_management_tab import render_ticker_management

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
        
        # Ticker selection - Get tickers from database
        db = Database()
        ticker_list = []
        default_ticker = os.getenv('DEFAULT_TICKER', 'AAPL')
        
        if db.connect():
            ticker_list = db.get_all_tickers()
            db.close()
        
        # If ticker list is available, use selectbox with search
        if ticker_list:
            # Get company names for tickers
            import yfinance as yf
            ticker_display_map = {}
            ticker_to_symbol = {}
            
            for symbol in ticker_list:
                try:
                    ticker_obj = yf.Ticker(symbol)
                    company_name = ticker_obj.info.get('longName', ticker_obj.info.get('shortName', symbol))
                    display_name = f"{company_name} ({symbol})"
                except:
                    display_name = symbol
                
                ticker_display_map[symbol] = display_name
                ticker_to_symbol[display_name] = symbol
            
            # Set default index
            default_index = 0
            display_options = [ticker_display_map[t] for t in ticker_list]
            
            if default_ticker in ticker_list:
                default_index = ticker_list.index(default_ticker)
            
            selected_display = st.selectbox(
                "Stock Ticker Selection",
                options=display_options,
                index=default_index,
                help="Search and select a stock ticker symbol"
            )
            
            # Get actual ticker symbol from selection
            ticker = ticker_to_symbol[selected_display]
        else:
            # Fallback to text input if no tickers in database
            ticker = st.text_input(
                "Stock Ticker",
                value=default_ticker,
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
    tab1, tab2, tab3 = st.tabs(["📊 Momentum Analysis", "🔮 Predictions", "⚙️ Manage Tickers"])
    
    with tab1:
        render_momentum_tab(ticker)
    
    with tab2:
        render_predictions_tab(ticker)
    
    with tab3:
        render_ticker_management()


if __name__ == "__main__":
    main()
