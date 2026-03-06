"""
Momentum tab for the dashboard.
Displays RSI and MACD indicators.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database
from models.models import calculate_indicators
from dashboard.utils import format_price, format_price_change, get_currency_info


def render_momentum_tab(ticker: str):
    """
    Render the momentum analysis tab.
    
    Args:
        ticker: Raw stock ticker symbol (no yfinance suffix)
    """
    # Maximize chart width — reduce Streamlit's default block-container padding
    st.markdown(
        """
        <style>
        .block-container { max-width: 98%; padding-left: 1rem; padding-right: 1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    yf_symbol = st.session_state.get("yf_symbol", ticker)

    # Get company name
    import yfinance as yf
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        company_name = ticker_obj.info.get('longName', ticker_obj.info.get('shortName', ticker))
    except:
        company_name = ticker
    
    st.header(f"Momentum Analysis for {company_name}")
    
    # Controls row
    col_tf, col_period, col_ma_type, col_ma_select, col_bb, col_sr_toggle, col_sr_levels = st.columns([1.5, 1.5, 1, 3, 1, 1.5, 0.5])
    with col_tf:
        timeframe = st.selectbox(
            "Timeframe",
            options=["5 Minutes", "15 Minutes", "30 Minutes", "1 Hour", "4 Hours", "1 Day", "1 Week"],
            index=5,  # Default to 1 Day
            help="Select data timeframe"
        )
    
    with col_period:
        # Period selector based on timeframe
        if timeframe in ["5 Minutes", "15 Minutes", "30 Minutes", "1 Hour", "4 Hours"]:
            period_options = ["1 Day", "2 Days", "3 Days", "5 Days", "10 Days", "15 Days", "1 Month", "Custom Range"]
            default_period = "5 Days"
        else:
            period_options = ["2 Days", "3 Days", "10 Days", "15 Days", "1 Month", "3 Months", "6 Months", "1 Year", "3 Years", "5 Years", "Max", "Custom Range"]
            default_period = "3 Months"
        
        period = st.selectbox(
            "Period",
            options=period_options,
            index=period_options.index(default_period) if default_period in period_options else 0,
            help="Historical period to display"
        )
    
    with col_ma_type:
        ma_types = st.multiselect(
            "MA Type",
            options=["SMA", "EMA"],
            default=["EMA"],
            help="Simple Moving Average (SMA) and/or Exponential Moving Average (EMA)"
        )
    
    with col_ma_select:
        ma_periods = st.multiselect(
            "Moving Averages",
            options=["5", "10", "20", "25", "50", "100", "200"],
            default=["5", "25", "200"],
            help="Select moving average periods to display on price chart"
        )
    
    with col_bb:
        show_bollinger = st.checkbox(
            "Bollinger Bands",
            value=False,
            help="20-period Bollinger Bands (±2 std dev)"
        )

    with col_sr_toggle:
        show_support_resistance = st.checkbox(
            "Support & Resistance",
            value=False,
            help="Display support and resistance levels based on local extrema"
        )
    
    with col_sr_levels:
        if show_support_resistance:
            sr_levels = st.selectbox(
                "Levels",
                options=[1, 2, 3, 4, 5],
                index=0,
                help="Number of support/resistance levels to display"
            )
        else:
            sr_levels = 1
    
    # Custom date range selector
    start_date = None
    end_date = None
    
    if period == "Custom Range":
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input(
                "Start Date",
                value=pd.Timestamp.now() - pd.Timedelta(days=30),
                help="Select start date for custom range"
            )
        with col_end:
            end_date = st.date_input(
                "End Date",
                value=pd.Timestamp.now(),
                help="Select end date for custom range"
            )
        st.info(f"📅 Custom range: {start_date} to {end_date}")
    
    # Map selections to yfinance parameters
    interval_map = {
        "5 Minutes": "5m",
        "15 Minutes": "15m",
        "30 Minutes": "30m",
        "1 Hour": "1h",
        "4 Hours": "4h",  
        "1 Day": "1d",
        "1 Week": "1wk"
    }
    
    period_map = {
        "1 Day": "1d",
        "2 Days": "2d",
        "3 Days": "3d",
        "5 Days": "5d",
        "10 Days": "10d",
        "15 Days": "15d",
        "1 Month": "1mo",
        "3 Months": "3mo",
        "6 Months": "6mo",
        "1 Year": "1y",
        "3 Years": "3y",
        "5 Years": "5y",
        "Max": "max"
    }
    
    interval = interval_map[timeframe]
    period_param = period_map.get(period)
    
    # Fetch data from yfinance directly for intraday
    import yfinance as yf
    
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        
        # Use custom date range if selected, otherwise use period
        if period == "Custom Range" and start_date and end_date:
            # Validate date range
            if start_date > end_date:
                st.error("Start date must be before end date")
                return
            
            df = ticker_obj.history(start=start_date, end=end_date, interval=interval)
        else:
            df = ticker_obj.history(period=period_param, interval=interval)
        
        if df.empty:
            st.warning(f"No data available for {ticker} with timeframe {timeframe}.")
            st.info("Try selecting a different timeframe or period.")
            return
        
        # Reset index to make datetime a column
        df = df.reset_index()
        
        # Rename columns for consistency
        date_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
        df = df.rename(columns={date_col: 'Date'})
        
        # Sort by date
        df = df.sort_values('Date')
        
        # Calculate moving averages if selected
        for ma_type in ma_types:
            for period in ma_periods:
                period_len = int(period)
                col_name = f"{ma_type}{period}"
                
                if ma_type == "EMA":
                    # Exponential Moving Average
                    df[col_name] = df['Close'].ewm(span=period_len, adjust=False).mean()
                else:
                    # Simple Moving Average (SMA)
                    df[col_name] = df['Close'].rolling(window=period_len).mean()
        
        # Calculate indicators
        indicators = calculate_indicators(df)
        df = pd.concat([df, indicators], axis=1)
        
        # Display current metrics + signal interpretation
        col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 1.5, 1.5, 1.5])
        
        with col1:
            current_price = df.iloc[-1]['Close']
            st.metric("Current Price", format_price(current_price, yf_symbol))

        with col2:
            if len(df) >= 2:
                prev_close = df.iloc[-2]['Close']
                price_change = df.iloc[-1]['Close'] - prev_close
                if prev_close != 0:
                    price_change_pct = (price_change / prev_close) * 100
                    change_label = f"{timeframe} Change"
                    price_change_str = format_price_change(price_change, yf_symbol)
                    arrow = "▲" if price_change >= 0 else "▼"
                    color = "#09ab3b" if price_change >= 0 else "#ff2b2b"
                    st.markdown(
                        f'<div style="font-size:0.875rem;color:rgba(49,51,63,0.6)">{change_label}</div>'
                        f'<div style="display:flex;align-items:baseline;gap:0.5rem">'
                        f'<span style="font-size:1.75rem;font-weight:700">{price_change_pct:.2f}%</span>'
                        f'<span style="font-size:1rem;color:{color}">{arrow} {price_change_str}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    price_change_str = format_price_change(price_change, yf_symbol)
                    st.metric(f"{timeframe} Change", "N/A", price_change_str)
            else:
                st.metric(f"{timeframe} Change", "N/A")

        with col3:
            # Linear regression slope over the full period as "Price Trend"
            if len(df) >= 3:
                closes = df['Close'].values
                x = np.arange(len(closes))
                slope, intercept = np.polyfit(x, closes, 1)
                # Express slope as % change per bar relative to first fitted value
                fitted_start = intercept
                if fitted_start != 0:
                    slope_pct = (slope / abs(fitted_start)) * 100
                else:
                    slope_pct = 0.0
                if slope_pct >= 0:
                    trend_text = "📈 Uptrend"
                    trend_color = "#09ab3b"
                else:
                    trend_text = "📉 Downtrend"
                    trend_color = "#ff2b2b"
                st.markdown(
                    f'<div style="font-size:0.875rem;color:rgba(49,51,63,0.6)">Price Trend</div>'
                    f'<div style="display:flex;align-items:baseline;gap:0.5rem">'
                    f'<span style="font-size:1.85rem;font-weight:700;color:{trend_color}">{trend_text}</span>'
                    f'<span style="font-size:1.75rem">{slope_pct:+.2f}%</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.metric("Price Trend", "N/A")

        with col4:
            if 'RSI' in df.columns and not pd.isna(df.iloc[-1]['RSI']):
                rsi_value = df.iloc[-1]['RSI']
                if rsi_value > 70:
                    signal_text = "🔴 Overbought"
                    signal_color = "#ff2b2b"
                elif rsi_value < 30:
                    signal_text = "🟢 Oversold"
                    signal_color = "#09ab3b"
                else:
                    signal_text = "🟡 Neutral"
                    signal_color = "#faca2b"
                st.markdown(
                    f'<div style="font-size:0.875rem;color:rgba(49,51,63,0.6)">RSI (14)</div>'
                    f'<div style="display:flex;align-items:baseline;gap:0.5rem">'
                    f'<span style="font-size:1.85rem;font-weight:700;color:{signal_color}">{signal_text}</span>'
                    f'<span style="font-size:1.75rem">{rsi_value:.2f}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.metric("RSI (14)", "N/A")

        with col5:
            if 'MACD' in df.columns and not pd.isna(df.iloc[-1]['MACD']):
                macd_value = df.iloc[-1]['MACD']
                if 'MACD_signal' in df.columns and not pd.isna(df.iloc[-1]['MACD_signal']):
                    signal_val = df.iloc[-1]['MACD_signal']
                    if macd_value > signal_val:
                        signal_text = "🟢 Bullish"
                        signal_color = "#09ab3b"
                    else:
                        signal_text = "🔴 Bearish"
                        signal_color = "#ff2b2b"
                else:
                    signal_text = ""
                    signal_color = "grey"
                st.markdown(
                    f'<div style="font-size:0.875rem;color:rgba(49,51,63,0.6)">MACD</div>'
                    f'<div style="display:flex;align-items:baseline;gap:0.5rem">'
                    f'<span style="font-size:1.85rem;font-weight:700;color:{signal_color}">{signal_text}</span>'
                    f'<span style="font-size:1.75rem;">{macd_value:.4f}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.metric("MACD", "N/A")


        
        st.divider()
        
        # Build a sequential integer index so the chart has no gaps
        # for weekends, holidays, or non-trading hours.
        df = df.reset_index(drop=True)
        x_idx = df.index  # 0, 1, 2, …

        # Formatted tick labels (show every ~Nth label to avoid clutter)
        is_intraday = timeframe in ["5 Minutes", "15 Minutes", "30 Minutes", "1 Hour", "4 Hours"]
        if is_intraday:
            tick_labels = df['Date'].dt.strftime('%m/%d %H:%M')
        else:
            tick_labels = df['Date'].dt.strftime('%Y-%m-%d')

        n_ticks = min(len(df), 40)  # show at most ~40 labels
        tick_step = max(1, len(df) // n_ticks)
        tick_vals = list(range(0, len(df), tick_step))
        tick_text = [tick_labels.iloc[i] for i in tick_vals]

        # Create subplots for price and indicators
        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=('Price', 'Volume', 'RSI', 'MACD'),
            row_heights=[1.0, 0.2, 0.25, 0.375]
        )
        
        # Price chart
        fig.add_trace(
            go.Candlestick(
                x=x_idx,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='Price',
                customdata=tick_labels.values,
                hoverinfo='text',
                text=[
                    f"{tick_labels.iloc[i]}<br>"
                    f"O: {df['Open'].iloc[i]:.2f}  H: {df['High'].iloc[i]:.2f}<br>"
                    f"L: {df['Low'].iloc[i]:.2f}  C: {df['Close'].iloc[i]:.2f}<br>"
                    f"Vol: {int(df['Volume'].iloc[i]):,}"
                    for i in range(len(df))
                ],
            ),
            row=1, col=1
        )
        
        # Add moving averages to price chart
        period_colors = {
            "5": "#FF6B6B",      # Red
            "10": "#FFA500",     # Orange
            "20": "#4ECDC4",     # Teal
            "25": "#FFD700",     # Gold
            "50": "#95E1D3",     # Light teal
            "100": "#9B59B6",    # Purple
            "200": "#3498DB"     # Blue
        }
        
        # Define line styles for SMA and EMA
        line_styles = {
            "SMA": "solid",
            "EMA": "dash"
        }
        
        for ma_type in ma_types:
            for period in ma_periods:
                col_name = f"{ma_type}{period}"
                if col_name in df.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=x_idx,
                            y=df[col_name],
                            name=col_name,
                            customdata=tick_labels.values,
                            hovertemplate='%{customdata}<br>%{y:.4f}<extra>%{fullData.name}</extra>',
                            line=dict(
                                color=period_colors.get(period, '#808080'),
                                width=1.5,
                                dash=line_styles.get(ma_type, 'solid')
                            ),
                            opacity=0.8
                        ),
                        row=1, col=1
                    )
        
        # Add Bollinger Bands if enabled
        if show_bollinger:
            bb_period = 20
            bb_std = 2
            bb_mid = df['Close'].rolling(window=bb_period).mean()
            bb_rolling_std = df['Close'].rolling(window=bb_period).std()
            bb_upper = bb_mid + bb_std * bb_rolling_std
            bb_lower = bb_mid - bb_std * bb_rolling_std

            fig.add_trace(
                go.Scatter(
                    x=x_idx, y=bb_upper, name='BB Upper',
                    line=dict(color='rgba(173,216,230,0.6)', width=1),
                    customdata=tick_labels.values,
                    hovertemplate='%{customdata}<br>BB Upper: %{y:.2f}<extra></extra>',
                ),
                row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=x_idx, y=bb_lower, name='BB Lower',
                    line=dict(color='rgba(173,216,230,0.6)', width=1),
                    fill='tonexty', fillcolor='rgba(173,216,230,0.12)',
                    customdata=tick_labels.values,
                    hovertemplate='%{customdata}<br>BB Lower: %{y:.2f}<extra></extra>',
                ),
                row=1, col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=x_idx, y=bb_mid, name='BB Mid',
                    line=dict(color='rgba(173,216,230,0.8)', width=1, dash='dot'),
                    customdata=tick_labels.values,
                    hovertemplate='%{customdata}<br>BB Mid: %{y:.2f}<extra></extra>',
                ),
                row=1, col=1,
            )

        # Add support and resistance levels if enabled
        if show_support_resistance:
            # Function to find local extrema
            def find_support_resistance_levels(df, num_levels=5, window=5):
                """
                Find support and resistance levels based on local extrema.
                
                Args:
                    df: DataFrame with High and Low columns
                    num_levels: Number of levels to find for each (support/resistance)
                    window: Window size for identifying local extrema
                
                Returns:
                    support_levels: List of support price levels (ascending)
                    resistance_levels: List of resistance price levels (descending)
                """
                import numpy as np
                
                # Find local minima for support (simple approach without scipy)
                support_candidates = []
                lows = df['Low'].values
                for i in range(window, len(lows) - window):
                    if all(lows[i] <= lows[i-window:i]) and all(lows[i] <= lows[i+1:i+window+1]):
                        support_candidates.append(lows[i])
                
                # Find local maxima for resistance
                resistance_candidates = []
                highs = df['High'].values
                for i in range(window, len(highs) - window):
                    if all(highs[i] >= highs[i-window:i]) and all(highs[i] >= highs[i+1:i+window+1]):
                        resistance_candidates.append(highs[i])
                
                # Always include absolute min/max
                support_candidates.append(df['Low'].min())
                resistance_candidates.append(df['High'].max())
                
                # Remove duplicates and sort
                support_candidates = sorted(set(support_candidates))
                resistance_candidates = sorted(set(resistance_candidates), reverse=True)
                
                # Get top N levels
                support_levels = support_candidates[:num_levels]
                resistance_levels = resistance_candidates[:num_levels]
                
                return support_levels, resistance_levels
            
            # Calculate support and resistance levels
            support_levels, resistance_levels = find_support_resistance_levels(df, num_levels=sr_levels, window=5)
            
            # Add support lines
            for i, support in enumerate(support_levels, 1):
                opacity = 0.7 - (i - 1) * 0.1  # Decreasing opacity for higher levels
                fig.add_hline(
                    y=support,
                    line_dash="dot",
                    line_color="green",
                    line_width=2,
                    opacity=max(opacity, 0.3),
                    annotation_text=f"S{i}: {format_price(support, yf_symbol)}",
                    annotation_position="right",
                    row=1, col=1
                )
            
            # Add resistance lines
            for i, resistance in enumerate(resistance_levels, 1):
                opacity = 0.7 - (i - 1) * 0.1  # Decreasing opacity for higher levels
                fig.add_hline(
                    y=resistance,
                    line_dash="dot",
                    line_color="red",
                    line_width=2,
                    opacity=max(opacity, 0.3),
                    annotation_text=f"R{i}: {format_price(resistance, yf_symbol)}",
                    annotation_position="right",
                    row=1, col=1
                )
        
        # Volume chart
        vol_colors = [
            '#26a69a' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ef5350'
            for i in range(len(df))
        ]
        fig.add_trace(
            go.Bar(
                x=x_idx, y=df['Volume'], name='Volume',
                marker_color=vol_colors, opacity=0.7,
                customdata=tick_labels.values,
                hovertemplate='%{customdata}<br>Vol: %{y:,.0f}<extra></extra>',
                showlegend=False,
            ),
            row=2, col=1,
        )

        # RSI chart
        if 'RSI' in df.columns:
            rsi_vals = df['RSI']
            # Overbought fill (above 70)
            rsi_above_70 = rsi_vals.where(rsi_vals >= 70)
            fig.add_trace(
                go.Scatter(
                    x=x_idx, y=[70] * len(df), mode='lines',
                    line=dict(width=0), showlegend=False, hoverinfo='skip',
                ),
                row=3, col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=x_idx, y=rsi_above_70, mode='lines',
                    line=dict(width=0), showlegend=False, hoverinfo='skip',
                    fill='tonexty', fillcolor='rgba(239,83,80,0.25)',
                ),
                row=3, col=1,
            )
            # Oversold fill (below 30)
            rsi_below_30 = rsi_vals.where(rsi_vals <= 30)
            fig.add_trace(
                go.Scatter(
                    x=x_idx, y=[30] * len(df), mode='lines',
                    line=dict(width=0), showlegend=False, hoverinfo='skip',
                ),
                row=3, col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=x_idx, y=rsi_below_30, mode='lines',
                    line=dict(width=0), showlegend=False, hoverinfo='skip',
                    fill='tonexty', fillcolor='rgba(38,166,154,0.25)',
                ),
                row=3, col=1,
            )
            # RSI line on top
            fig.add_trace(
                go.Scatter(
                    x=x_idx, y=rsi_vals, name='RSI', line=dict(color='purple'),
                    customdata=tick_labels.values,
                    hovertemplate='%{customdata}<br>RSI: %{y:.2f}<extra></extra>',
                ),
                row=3, col=1
            )
            # Add RSI reference lines
            fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)
        
        # MACD chart
        if 'MACD' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=x_idx, y=df['MACD'], name='MACD', line=dict(color='blue'),
                    customdata=tick_labels.values,
                    hovertemplate='%{customdata}<br>MACD: %{y:.4f}<extra></extra>',
                ),
                row=4, col=1
            )
            fig.add_trace(
                go.Scatter(
                    x=x_idx, y=df['MACD_signal'], name='Signal', line=dict(color='orange'),
                    customdata=tick_labels.values,
                    hovertemplate='%{customdata}<br>Signal: %{y:.4f}<extra></extra>',
                ),
                row=4, col=1
            )
            hist_vals = df['MACD_hist'].values
            # Color by direction: bright when diverging from center,
            # lighter when converging (compared to previous bar).
            hist_colors = []
            for i, v in enumerate(hist_vals):
                prev = hist_vals[i - 1] if i > 0 else 0
                diverging = abs(v) >= abs(prev)
                if v >= 0:
                    hist_colors.append('#26a69a' if diverging else '#b2dfdb')
                else:
                    hist_colors.append('#ef5350' if diverging else '#ef9a9a')
            fig.add_trace(
                go.Bar(
                    x=x_idx, y=df['MACD_hist'], name='Histogram',
                    marker_color=hist_colors,
                    customdata=tick_labels.values,
                    hovertemplate='%{customdata}<br>Hist: %{y:.4f}<extra></extra>',
                ),
                row=4, col=1
            )
        
        # Update layout
        fig.update_layout(
            height=1100,
            showlegend=True,
            xaxis_rangeslider_visible=False,
            hovermode='closest',
            spikedistance=-1,
        )
        # Spike crosshair on all x-axes
        for ax in ['xaxis', 'xaxis2', 'xaxis3', 'xaxis4']:
            fig.update_layout(**{ax: dict(
                showspikes=True, spikemode='across', spikethickness=0.5,
                spikecolor='grey', spikedash='dot',
            )})
        
        # Apply categorical tick labels on the price chart (row 1)
        fig.update_xaxes(
            tickvals=tick_vals,
            ticktext=tick_text,
            tickangle=-45,
            row=1, col=1,
        )
        # Hide tick labels on Volume, RSI and MACD subplots
        fig.update_xaxes(showticklabels=False, row=2, col=1)
        fig.update_xaxes(showticklabels=False, row=3, col=1)
        fig.update_xaxes(showticklabels=False, row=4, col=1)

        fig.update_yaxes(title_text=f"Price ({get_currency_info(yf_symbol)[0]})", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        fig.update_yaxes(title_text="RSI", row=3, col=1)
        fig.update_yaxes(title_text="MACD", row=4, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
    
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.info("Try selecting a different timeframe or ticker.")
