"""
Ticker management tab for the dashboard.
Add, remove, and manage tracked tickers.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database
from shared.config import to_yf_symbol


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
        
        all_tickers = db.get_all_tickers()       # list[dict] with 'symbol','region'
        active_tickers = db.get_active_tickers()  # list[dict]
        active_symbols = {t['symbol'] for t in active_tickers}
        
        if all_tickers:
            # Create a table showing ticker status
            import pandas as pd
            ticker_data = []
            for t in all_tickers:
                sym, reg = t['symbol'], t['region']
                yf_sym = to_yf_symbol(sym, reg)
                status = "✅ Active" if sym in active_symbols else "🔴 Inactive"
                ticker_data.append({
                    "Symbol": sym,
                    "Region": reg,
                    "yfinance": yf_sym,
                    "Status": status,
                })
            
            df = pd.DataFrame(ticker_data)
            st.dataframe(df[['Symbol', 'Region', 'yfinance', 'Status']], use_container_width=True, hide_index=True)
            
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
        
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            new_ticker = st.text_input(
                "Ticker Symbol",
                placeholder="e.g., AAPL, 069500, 7203",
                help="Enter the raw symbol without market suffix",
            ).upper().strip()
        with col2:
            region = st.selectbox(
                "Market Region",
                options=["US", "KR", "JP", "GLOBAL"],
                index=0,
                help="Select the market region for this ticker",
            )
        with col3:
            st.write("")  # Spacer
            st.write("")  # Spacer
            add_button = st.button("Add Ticker", type="primary", use_container_width=True)
        
        if add_button:
            if new_ticker:
                # Validate ticker exists via yfinance using combined symbol
                import yfinance as yf
                yf_sym = to_yf_symbol(new_ticker, region)
                try:
                    info = yf.Ticker(yf_sym).info
                    price_keys = ("trailingPegRatio", "regularMarketPrice", "currentPrice", "previousClose")
                    has_price_data = any(info.get(k) is not None for k in price_keys)
                    if not info or not has_price_data:
                        raise ValueError("no price data")
                    db.add_ticker(new_ticker, region=region)
                    name = info.get("longName", info.get("shortName", new_ticker))
                    st.success(f"✅ Added ticker: **{new_ticker}** ({region}) — {name}")
                    st.rerun()
                except Exception:
                    st.error(
                        f"❌ Could not find **{yf_sym}** on yfinance. "
                        "Please verify the symbol and region are correct."
                    )
            else:
                st.warning("Please enter a ticker symbol")
        
        st.divider()
        
        # Deactivate ticker
        if all_tickers:
            st.subheader("🔴 Deactivate Ticker")
            st.caption("Deactivated tickers will stop updating but historical data is preserved")
            
            active_labels = [f"{t['symbol']} ({t['region']})" for t in active_tickers]
            col1, col2 = st.columns([3, 1])
            with col1:
                ticker_to_deactivate = st.selectbox(
                    "Select ticker to deactivate",
                    options=active_labels if active_labels else ["No active tickers"],
                    disabled=not active_labels
                )
            with col2:
                st.write("")  # Spacer
                st.write("")  # Spacer
                deactivate_button = st.button(
                    "Deactivate", 
                    type="secondary", 
                    use_container_width=True,
                    disabled=not active_labels
                )
            
            if deactivate_button and active_labels:
                raw_symbol = ticker_to_deactivate.split(" (")[0]
                db.deactivate_ticker(raw_symbol)
                st.success(f"✅ Deactivated ticker: {raw_symbol}")
                st.rerun()
            
            st.divider()
            
            # Reactivate ticker
            inactive_tickers = [t for t in all_tickers if t['symbol'] not in active_symbols]
            if inactive_tickers:
                st.subheader("✅ Reactivate Ticker")
                st.caption("Resume tracking a previously deactivated ticker")
                
                inactive_labels = [f"{t['symbol']} ({t['region']})" for t in inactive_tickers]
                col1, col2 = st.columns([3, 1])
                with col1:
                    ticker_to_reactivate = st.selectbox(
                        "Select ticker to reactivate",
                        options=inactive_labels
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
                    raw_symbol = ticker_to_reactivate.split(" (")[0]
                    db.add_ticker(raw_symbol)  # add_ticker reactivates if exists
                    st.success(f"✅ Reactivated ticker: {raw_symbol}")
                    st.rerun()
        
        st.divider()
        
        # Information
        st.subheader("ℹ️ Information")
        st.info(
            """
            **How it works:**
            - Enter the raw symbol (e.g. `069500`) and select the market region (e.g. `KR`).
            - The system automatically builds the yfinance symbol (e.g. `069500.KS`) for data fetching.
            
            **Region → yfinance suffix:**
            - **US**: no suffix (`AAPL` → `AAPL`)
            - **KR**: `.KS` (`069500` → `069500.KS`)
            - **JP**: `.T` (`7203` → `7203.T`)
            - **GLOBAL**: no suffix
            
            **Note:** Deactivated tickers stop receiving updates but keep all historical data.
            You can reactivate them anytime to resume tracking.
            """
        )
        
    finally:
        db.close()
