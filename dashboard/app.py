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
from dashboard.ai_advisor_tab import render_ai_advisor_tab
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
    </style>
    """, unsafe_allow_html=True)


def main():
    """Main dashboard application."""
    
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

        # Page navigation
        _nav_options = [
            "🎯 Directional Outlook",
            "📊 Momentum Analysis",
            "🤖 AI Advisor (Gen Prompt)",
            "⚙️ Manage Tickers",
        ]
        page = st.pills(
            "Navigation",
            options=_nav_options,
            default=_nav_options[0],
            label_visibility="collapsed",
        )
        if page is None:
            page = _nav_options[0]
        
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
            "and XGBoost-based directional probability scores for stocks."
        )
    
    # Main content area — render selected page
    if page == "📊 Momentum Analysis":
        render_momentum_tab(ticker)
    elif page == "🎯 Directional Outlook":
        render_predictions_tab(ticker)
    elif page == "🤖 AI Advisor (Gen Prompt)":
        render_ai_advisor_tab(ticker)
    elif page == "⚙️ Manage Tickers":
        render_ticker_management()


if __name__ == "__main__":
    main()
