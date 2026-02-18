"""
Momentum tab for the dashboard.
Displays RSI and MACD indicators.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database
from models.models import calculate_indicators


def render_momentum_tab(ticker: str):
    """
    Render the momentum analysis tab.
    
    Args:
        ticker: Stock ticker symbol
    """
    st.header(f"Momentum Analysis for {ticker}")
    
    # Connect to database and fetch data
    db = Database()
    if not db.connect():
        st.error("Failed to connect to database")
        return
    
    try:
        # Fetch daily prices
        daily_prices = db.get_daily_prices(ticker, limit=100)
        
        if not daily_prices:
            st.warning(f"No data available for {ticker}. Data ingestion may still be in progress.")
            st.info("Please wait for the scheduler to fetch data, or run the ingestion manually.")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(daily_prices)
        df = df.sort_values('date')
        
        # Calculate indicators
        indicators = calculate_indicators(df)
        df = pd.concat([df, indicators], axis=1)
        
        # Display current metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            current_price = df.iloc[-1]['close']
            st.metric("Current Price", f"${current_price:.2f}")
        
        with col2:
            if 'RSI' in df.columns and not pd.isna(df.iloc[-1]['RSI']):
                rsi_value = df.iloc[-1]['RSI']
                st.metric("RSI (14)", f"{rsi_value:.2f}")
            else:
                st.metric("RSI (14)", "N/A")
        
        with col3:
            if 'MACD' in df.columns and not pd.isna(df.iloc[-1]['MACD']):
                macd_value = df.iloc[-1]['MACD']
                st.metric("MACD", f"{macd_value:.4f}")
            else:
                st.metric("MACD", "N/A")
        
        with col4:
            price_change = df.iloc[-1]['close'] - df.iloc[-2]['close']
            price_change_pct = (price_change / df.iloc[-2]['close']) * 100
            st.metric("Daily Change", f"{price_change_pct:.2f}%", f"${price_change:.2f}")
        
        st.divider()
        
        # Create subplots for price and indicators
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=('Price', 'RSI', 'MACD'),
            row_heights=[0.5, 0.25, 0.25]
        )
        
        # Price chart
        fig.add_trace(
            go.Candlestick(
                x=df['date'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price'
            ),
            row=1, col=1
        )
        
        # RSI chart
        if 'RSI' in df.columns:
            fig.add_trace(
                go.Scatter(x=df['date'], y=df['RSI'], name='RSI', line=dict(color='purple')),
                row=2, col=1
            )
            # Add RSI reference lines
            fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=2, col=1)
        
        # MACD chart
        if 'MACD' in df.columns:
            fig.add_trace(
                go.Scatter(x=df['date'], y=df['MACD'], name='MACD', line=dict(color='blue')),
                row=3, col=1
            )
            fig.add_trace(
                go.Scatter(x=df['date'], y=df['MACD_signal'], name='Signal', line=dict(color='orange')),
                row=3, col=1
            )
            fig.add_trace(
                go.Bar(x=df['date'], y=df['MACD_hist'], name='Histogram', marker_color='gray'),
                row=3, col=1
            )
        
        # Update layout
        fig.update_layout(
            height=800,
            showlegend=True,
            xaxis_rangeslider_visible=False,
            hovermode='x unified'
        )
        
        fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        fig.update_yaxes(title_text="RSI", row=2, col=1)
        fig.update_yaxes(title_text="MACD", row=3, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Analysis interpretation
        st.subheader("Signal Interpretation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**RSI Analysis:**")
            if 'RSI' in df.columns and not pd.isna(df.iloc[-1]['RSI']):
                rsi = df.iloc[-1]['RSI']
                if rsi > 70:
                    st.warning("🔴 Overbought - RSI above 70. Consider selling.")
                elif rsi < 30:
                    st.success("🟢 Oversold - RSI below 30. Consider buying.")
                else:
                    st.info("🟡 Neutral - RSI in normal range (30-70).")
            else:
                st.info("Not enough data to calculate RSI.")
        
        with col2:
            st.write("**MACD Analysis:**")
            if 'MACD' in df.columns and 'MACD_signal' in df.columns:
                macd = df.iloc[-1]['MACD']
                signal = df.iloc[-1]['MACD_signal']
                if not pd.isna(macd) and not pd.isna(signal):
                    if macd > signal:
                        st.success("🟢 Bullish - MACD above signal line.")
                    else:
                        st.warning("🔴 Bearish - MACD below signal line.")
                else:
                    st.info("Not enough data to calculate MACD.")
            else:
                st.info("Not enough data to calculate MACD.")
        
    finally:
        db.close()
