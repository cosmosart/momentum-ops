"""
Ticker management tab for the dashboard.
Add, remove, and manage tracked tickers.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database


def render_ticker_management():
    """Render the ticker management interface."""
    st.header("📋 Ticker Management")
    
    # Connect to database
    db = Database()
    if not db.connect():
        st.error("Failed to connect to database")
        return
    
    try:
        # Display current tickers
        st.subheader("Current Tickers")
        
        all_tickers = db.get_all_tickers()
        active_tickers = db.get_active_tickers()
        
        if all_tickers:
            # Create a table showing ticker status
            ticker_data = []
            for ticker in all_tickers:
                status = "✅ Active" if ticker in active_tickers else "🔴 Inactive"
                ticker_data.append({
                    "Ticker": ticker,
                    "Status": status,
                    "Active": ticker in active_tickers
                })
            
            # Display as dataframe
            import pandas as pd
            df = pd.DataFrame(ticker_data)
            st.dataframe(df[['Ticker', 'Status']], use_container_width=True, hide_index=True)
            
            st.metric("Total Tickers", len(all_tickers))
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Active", len(active_tickers))
            with col2:
                st.metric("Inactive", len(all_tickers) - len(active_tickers))
        else:
            st.info("No tickers configured yet. Add your first ticker below.")
        
        st.divider()
        
        # Add new ticker
        st.subheader("➕ Add New Ticker")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            new_ticker = st.text_input(
                "Ticker Symbol",
                placeholder="e.g., AAPL, 1542.T, GOOGL",
                help="Enter stock ticker symbol. Examples: AAPL (US), 1542.T (Japan), 005930.KS (Korea)"
            ).upper().strip()
        with col2:
            st.write("")  # Spacer
            st.write("")  # Spacer
            add_button = st.button("Add Ticker", type="primary", use_container_width=True)
        
        if add_button:
            if new_ticker:
                # Validate ticker exists via yfinance
                import yfinance as yf
                try:
                    info = yf.Ticker(new_ticker).info
                    # yfinance returns a near-empty dict for invalid symbols
                    if not info or info.get("trailingPegRatio") is None and info.get("regularMarketPrice") is None and info.get("currentPrice") is None and info.get("previousClose") is None:
                        raise ValueError("no price data")
                    db.add_ticker(new_ticker)
                    name = info.get("longName", info.get("shortName", new_ticker))
                    st.success(f"✅ Added ticker: **{new_ticker}** ({name})")
                    st.rerun()
                except Exception:
                    st.error(
                        f"❌ Ticker **{new_ticker}** could not be found. "
                        "Please verify the symbol is valid (e.g. AAPL, 7203.T, 005930.KS)."
                    )
            else:
                st.warning("Please enter a ticker symbol")
        
        st.divider()
        
        # Deactivate ticker
        if all_tickers:
            st.subheader("🔴 Deactivate Ticker")
            st.caption("Deactivated tickers will stop updating but historical data is preserved")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                ticker_to_deactivate = st.selectbox(
                    "Select ticker to deactivate",
                    options=active_tickers if active_tickers else ["No active tickers"],
                    disabled=not active_tickers
                )
            with col2:
                st.write("")  # Spacer
                st.write("")  # Spacer
                deactivate_button = st.button(
                    "Deactivate", 
                    type="secondary", 
                    use_container_width=True,
                    disabled=not active_tickers
                )
            
            if deactivate_button and active_tickers:
                db.deactivate_ticker(ticker_to_deactivate)
                st.success(f"✅ Deactivated ticker: {ticker_to_deactivate}")
                st.rerun()
            
            st.divider()
            
            # Reactivate ticker
            inactive_tickers = [t for t in all_tickers if t not in active_tickers]
            if inactive_tickers:
                st.subheader("✅ Reactivate Ticker")
                st.caption("Resume tracking a previously deactivated ticker")
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    ticker_to_reactivate = st.selectbox(
                        "Select ticker to reactivate",
                        options=inactive_tickers
                    )
                with col2:
                    st.write("")  # Spacer
                    st.write("")  # Spacer
                    reactivate_button = st.button(
                        "Reactivate", 
                        type="primary", 
                        use_container_width=True
                    )
                
                if reactivate_button:
                    db.add_ticker(ticker_to_reactivate)  # add_ticker reactivates if exists
                    st.success(f"✅ Reactivated ticker: {ticker_to_reactivate}")
                    st.rerun()
        
        st.divider()
        
        # Information
        st.subheader("ℹ️ Information")
        st.info(
            """
            **Ticker Format Examples:**
            - US Stocks: `AAPL`, `GOOGL`, `MSFT`
            - Japanese Stocks: `1542.T`, `7203.T`, `6758.T`
            - Korean Stocks: `005930.KS`, `000660.KS`
            - Hong Kong Stocks: `0700.HK`, `9988.HK`
            
            **Note:** Deactivated tickers stop receiving updates but keep all historical data.
            You can reactivate them anytime to resume tracking.
            """
        )
        
    finally:
        db.close()
