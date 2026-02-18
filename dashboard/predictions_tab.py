"""
Predictions tab for the dashboard.
Displays price predictions for 1d, 1w, 1m, 1y timeframes.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database


def render_predictions_tab(ticker: str):
    """
    Render the predictions tab.
    
    Args:
        ticker: Stock ticker symbol
    """
    st.header(f"Price Predictions for {ticker}")
    
    st.info("⚠️ Note: Current predictions use placeholder algorithms. "
            "For production, implement proper ML models in models/models.py")
    
    # Connect to database and fetch data
    db = Database()
    if not db.connect():
        st.error("Failed to connect to database")
        return
    
    try:
        # Fetch analysis data
        analysis_data = db.get_analysis(ticker, limit=1)
        
        # Fetch price data for chart
        daily_prices = db.get_daily_prices(ticker, limit=30)
        
        if not daily_prices:
            st.warning(f"No data available for {ticker}. Data ingestion may still be in progress.")
            st.info("Please wait for the scheduler to fetch data, or run the ingestion manually.")
            return
        
        # Current price
        df_prices = pd.DataFrame(daily_prices)
        current_price = df_prices.iloc[0]['close']
        
        st.subheader("Current Price")
        st.metric("Price", f"${current_price:.2f}")
        
        st.divider()
        
        # Predictions
        st.subheader("Forecasted Prices")
        
        if analysis_data:
            analysis = analysis_data[0]
            
            # Display predictions in columns
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                pred_1d = analysis.get('prediction_1d')
                if pred_1d is not None and current_price != 0:
                    change_1d = pred_1d - current_price
                    change_pct_1d = (change_1d / current_price) * 100
                    st.metric(
                        "1 Day",
                        f"${pred_1d:.2f}",
                        f"{change_pct_1d:.2f}%"
                    )
                elif pred_1d is not None:
                    st.metric("1 Day", f"${pred_1d:.2f}")
                else:
                    st.metric("1 Day", "N/A")
            
            with col2:
                pred_1w = analysis.get('prediction_1w')
                if pred_1w is not None and current_price != 0:
                    change_1w = pred_1w - current_price
                    change_pct_1w = (change_1w / current_price) * 100
                    st.metric(
                        "1 Week",
                        f"${pred_1w:.2f}",
                        f"{change_pct_1w:.2f}%"
                    )
                elif pred_1w is not None:
                    st.metric("1 Week", f"${pred_1w:.2f}")
                else:
                    st.metric("1 Week", "N/A")
            
            with col3:
                pred_1m = analysis.get('prediction_1m')
                if pred_1m is not None and current_price != 0:
                    change_1m = pred_1m - current_price
                    change_pct_1m = (change_1m / current_price) * 100
                    st.metric(
                        "1 Month",
                        f"${pred_1m:.2f}",
                        f"{change_pct_1m:.2f}%"
                    )
                elif pred_1m is not None:
                    st.metric("1 Month", f"${pred_1m:.2f}")
                else:
                    st.metric("1 Month", "N/A")
            
            with col4:
                pred_1y = analysis.get('prediction_1y')
                if pred_1y is not None and current_price != 0:
                    change_1y = pred_1y - current_price
                    change_pct_1y = (change_1y / current_price) * 100
                    st.metric(
                        "1 Year",
                        f"${pred_1y:.2f}",
                        f"{change_pct_1y:.2f}%"
                    )
                elif pred_1y is not None:
                    st.metric("1 Year", f"${pred_1y:.2f}")
                else:
                    st.metric("1 Year", "N/A")
            
            st.divider()
            
            # Visualization
            st.subheader("Price Forecast Chart")
            
            # Prepare data for chart
            df_prices = df_prices.sort_values('date')
            
            # Create forecast points
            forecast_data = []
            if pred_1d is not None:
                forecast_data.append({'days': 1, 'price': pred_1d, 'label': '1 Day'})
            if pred_1w is not None:
                forecast_data.append({'days': 7, 'price': pred_1w, 'label': '1 Week'})
            if pred_1m is not None:
                forecast_data.append({'days': 30, 'price': pred_1m, 'label': '1 Month'})
            if pred_1y is not None:
                forecast_data.append({'days': 365, 'price': pred_1y, 'label': '1 Year'})
            
            # Create figure
            fig = go.Figure()
            
            # Historical prices
            fig.add_trace(go.Scatter(
                x=df_prices['date'],
                y=df_prices['close'],
                mode='lines',
                name='Historical Price',
                line=dict(color='blue', width=2)
            ))
            
            # Add current price point
            fig.add_trace(go.Scatter(
                x=[df_prices.iloc[-1]['date']],
                y=[current_price],
                mode='markers',
                name='Current Price',
                marker=dict(color='green', size=10)
            ))
            
            # Add prediction points (relative to last date)
            if forecast_data:
                last_date = pd.to_datetime(df_prices.iloc[-1]['date'])
                pred_dates = [last_date + pd.Timedelta(days=f['days']) for f in forecast_data]
                pred_prices = [f['price'] for f in forecast_data]
                pred_labels = [f['label'] for f in forecast_data]
                
                fig.add_trace(go.Scatter(
                    x=pred_dates,
                    y=pred_prices,
                    mode='markers+text',
                    name='Predictions',
                    marker=dict(color='red', size=10),
                    text=pred_labels,
                    textposition='top center'
                ))
            
            fig.update_layout(
                title=f"{ticker} Price History and Predictions",
                xaxis_title="Date",
                yaxis_title="Price ($)",
                height=500,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning("No prediction data available yet. Data ingestion may still be in progress.")
        
        # Disclaimer
        st.divider()
        st.caption(
            "⚠️ **Disclaimer:** These predictions are generated by placeholder algorithms "
            "and should not be used for actual trading decisions. "
            "Implement proper machine learning models for production use."
        )
        
    finally:
        db.close()
