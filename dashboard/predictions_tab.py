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
from dashboard.utils import format_price, get_currency_info


def render_predictions_tab(ticker: str):
    """
    Render the predictions tab.
    
    Args:
        ticker: Stock ticker symbol
    """
    # Get company name
    import yfinance as yf
    try:
        ticker_obj = yf.Ticker(ticker)
        company_name = ticker_obj.info.get('longName', ticker_obj.info.get('shortName', ticker))
    except:
        company_name = ticker
    
    st.header(f"Price Predictions for {company_name}")
    
    st.info("📊 Predictions use polynomial regression to capture non-linear price trends. "
            "Results include trend acceleration/deceleration patterns.")
    
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
        
        # Convert decimal columns to float for calculations
        df_prices['close'] = df_prices['close'].astype(float)
        if 'open' in df_prices.columns:
            df_prices['open'] = df_prices['open'].astype(float)
        if 'high' in df_prices.columns:
            df_prices['high'] = df_prices['high'].astype(float)
        if 'low' in df_prices.columns:
            df_prices['low'] = df_prices['low'].astype(float)
        
        current_price = df_prices.iloc[0]['close']
        
        st.subheader("Current Price")
        st.metric("Price", format_price(current_price, ticker))
        
        st.divider()
        
        # Predictions
        st.subheader("Forecasted Prices")
        
        # Model information
        with st.expander("📊 Model Information", expanded=False):
            st.write("**Model Type:** Polynomial Regression (Non-linear)")
            st.write("**Features:**")
            st.markdown("""
            - Captures trend acceleration/deceleration
            - Adapts polynomial degree based on data length
            - Includes volatility-based dampening for long-term predictions
            - Prevents unrealistic extrapolations with smart bounds
            """)
        
        if analysis_data:
            analysis = analysis_data[0]
            
            # Convert prediction values to float
            pred_1d = float(analysis.get('prediction_1d')) if analysis.get('prediction_1d') is not None else None
            pred_1w = float(analysis.get('prediction_1w')) if analysis.get('prediction_1w') is not None else None
            pred_1m = float(analysis.get('prediction_1m')) if analysis.get('prediction_1m') is not None else None
            pred_1y = float(analysis.get('prediction_1y')) if analysis.get('prediction_1y') is not None else None
            
            # Display predictions in columns
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if pred_1d is not None and current_price != 0:
                    change_1d = pred_1d - current_price
                    change_pct_1d = (change_1d / current_price) * 100
                    st.metric(
                        "1 Day",
                        format_price(pred_1d, ticker),
                        f"{change_pct_1d:.2f}%"
                    )
                elif pred_1d is not None:
                    st.metric("1 Day", format_price(pred_1d, ticker))
                else:
                    st.metric("1 Day", "N/A")
            
            with col2:
                if pred_1w is not None and current_price != 0:
                    change_1w = pred_1w - current_price
                    change_pct_1w = (change_1w / current_price) * 100
                    st.metric(
                        "1 Week",
                        format_price(pred_1w, ticker),
                        f"{change_pct_1w:.2f}%"
                    )
                elif pred_1w is not None:
                    st.metric("1 Week", format_price(pred_1w, ticker))
                else:
                    st.metric("1 Week", "N/A")
            
            with col3:
                if pred_1m is not None and current_price != 0:
                    change_1m = pred_1m - current_price
                    change_pct_1m = (change_1m / current_price) * 100
                    st.metric(
                        "1 Month",
                        format_price(pred_1m, ticker),
                        f"{change_pct_1m:.2f}%"
                    )
                elif pred_1m is not None:
                    st.metric("1 Month", format_price(pred_1m, ticker))
                else:
                    st.metric("1 Month", "N/A")
            
            with col4:
                if pred_1y is not None and current_price != 0:
                    change_1y = pred_1y - current_price
                    change_pct_1y = (change_1y / current_price) * 100
                    st.metric(
                        "1 Year",
                        format_price(pred_1y, ticker),
                        f"{change_pct_1y:.2f}%"
                    )
                elif pred_1y is not None:
                    st.metric("1 Year", format_price(pred_1y, ticker))
                else:
                    st.metric("1 Year", "N/A")
            
            st.divider()
            
            # Visualization
            st.subheader("Price Forecast Chart")
            
            # Confidence interval selector
            confidence_level = st.slider(
                "Confidence Interval (%)",
                min_value=5,
                max_value=30,
                value=15,
                step=5,
                help="Percentage range for upper and lower price projections"
            )
            
            # Prepare data for chart
            df_prices = df_prices.sort_values('date')
            
            # Calculate historical volatility for more realistic bounds
            df_prices['returns'] = df_prices['close'].pct_change()
            volatility = df_prices['returns'].std()
            
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
            
            # Add prediction points with confidence intervals
            if forecast_data:
                last_date = pd.to_datetime(df_prices.iloc[-1]['date'])
                
                # Add current point to start of forecast
                pred_dates = [last_date] + [last_date + pd.Timedelta(days=f['days']) for f in forecast_data]
                pred_prices = [current_price] + [f['price'] for f in forecast_data]
                
                # Calculate upper and lower bounds
                # Use sliding scale: more uncertainty for longer projections
                upper_bounds = [current_price]
                lower_bounds = [current_price]
                
                for i, f in enumerate(forecast_data):
                    # Increase uncertainty with time
                    time_factor = 1 + (f['days'] / 365) * 0.5  # Up to 50% more uncertainty for 1 year
                    uncertainty = (confidence_level / 100) * time_factor
                    
                    upper_bounds.append(f['price'] * (1 + uncertainty))
                    lower_bounds.append(f['price'] * (1 - uncertainty))
                
                # Add upper bound
                fig.add_trace(go.Scatter(
                    x=pred_dates,
                    y=upper_bounds,
                    mode='lines',
                    name='Upper Projection',
                    line=dict(color='rgba(255, 0, 0, 0.3)', width=1, dash='dash'),
                    showlegend=True
                ))
                
                # Add lower bound
                fig.add_trace(go.Scatter(
                    x=pred_dates,
                    y=lower_bounds,
                    mode='lines',
                    name='Lower Projection',
                    line=dict(color='rgba(255, 0, 0, 0.3)', width=1, dash='dash'),
                    fill='tonexty',
                    fillcolor='rgba(255, 0, 0, 0.1)',
                    showlegend=True
                ))
                
                # Add predicted line
                fig.add_trace(go.Scatter(
                    x=pred_dates,
                    y=pred_prices,
                    mode='lines+markers',
                    name='Forecast',
                    line=dict(color='red', width=2, dash='dot'),
                    marker=dict(color='red', size=8)
                ))
                
                # Add labels for prediction points (skip current price)
                pred_labels = [f['label'] for f in forecast_data]
                fig.add_trace(go.Scatter(
                    x=pred_dates[1:],
                    y=pred_prices[1:],
                    mode='text',
                    name='Labels',
                    text=pred_labels,
                    textposition='top center',
                    showlegend=False
                ))
            
            fig.update_layout(
                title=f"Price Forecast with {confidence_level}% Confidence Interval",
                xaxis_title="Date",
                yaxis_title=f"Price ({get_currency_info(ticker)[0]})",
                height=600,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning("No prediction data available yet. Data ingestion may still be in progress.")
        
        # Disclaimer
        st.divider()
        st.caption(
            "⚠️ **Disclaimer:** Predictions are generated using polynomial regression models "
            "and should be used for informational purposes only. "
            "Past performance does not guarantee future results. Not financial advice."
        )
        
    finally:
        db.close()
