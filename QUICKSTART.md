# Quick Start Guide - Momentum Ops

## � Prerequisites

- **Docker & Docker Compose** (recommended - handles all dependencies)
- **OR for local development:**
  - Python 3.13+
  - PostgreSQL 18+

**Technology Stack:**
- Backend: Python 3.13 with psycopg3 driver
- Database: PostgreSQL 18
- Dashboard: Streamlit 1.40.0+

---

## 🚀 Fastest Way to Get Started

### Using Docker (Recommended)

1. **Clone and Navigate**
   ```bash
   git clone https://github.com/cosmosart/momentum-ops.git
   cd momentum-ops
   ```

2. **Create Environment File**
   ```bash
   cp .env.example .env
   ```
   
   Optionally edit `.env` to customize:
   - `DEFAULT_TICKER=AAPL` (change to any stock ticker)
   - `UPDATE_INTERVAL_MINUTES=5` (data refresh frequency)

3. **Start Application**
   ```bash
   docker-compose up -d
   ```

4. **Access Dashboard**
   - Open browser: http://localhost:8501
   - Wait 1-2 minutes for initial data ingestion

5. **View Logs** (optional)
   ```bash
   docker-compose logs -f
   ```

6. **Stop Application**
   ```bash
   docker-compose down
   ```

---

## 📊 Using the Dashboard

### Momentum Analysis Tab
- **Candlestick Chart**: Visual price movements
- **RSI Indicator**: Overbought (>70) / Oversold (<30) signals
- **MACD Indicator**: Trend direction and momentum
- **Signal Interpretation**: Automated buy/sell signals

### Predictions Tab
- **1 Day, 1 Week, 1 Month, 1 Year** forecasts
- **Visual Chart**: Historical prices + predictions
- **Price Changes**: Percentage and dollar changes

---

## 🔧 Troubleshooting

### "No data available"
- **Wait**: Initial data fetch takes 1-2 minutes
- **Check Logs**: `docker-compose logs scheduler`
- **Restart**: `docker-compose restart scheduler`

### "Database connection failed"
- **Wait**: Database takes ~10 seconds to initialize
- **Verify**: `docker-compose ps` (all services should be "Up")
- **Restart**: `docker-compose down && docker-compose up -d`

### Invalid ticker
- **Verify**: Ticker exists on Yahoo Finance
- **Use**: Major stocks (AAPL, GOOGL, MSFT, TSLA, etc.)
- **Format**: Always uppercase

---

## 🎯 What to Try

1. **Compare Stocks**
   - Enter different tickers in sidebar
   - Compare RSI and MACD signals
   - Check prediction trends

2. **Analyze Signals**
   - RSI > 70: Consider selling (overbought)
   - RSI < 30: Consider buying (oversold)
   - MACD above signal: Bullish trend
   - MACD below signal: Bearish trend

3. **Monitor Multiple Stocks**
   - Add more tickers to `.env` (coming soon)
   - Use multiple browser tabs
   - Compare momentum across sectors

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────┐
│         Streamlit Dashboard             │  Port 8501
│  (Momentum + Predictions Tabs)          │
│         [Python 3.13]                   │
└────────────────┬────────────────────────┘
                 │ psycopg3
┌────────────────▼────────────────────────┐
│       PostgreSQL 18 Database            │  Port 5432
│  (price_realtime, price_daily,          │
│   analysis_info tables)                 │
└────────────────▲────────────────────────┘
                 │
┌────────────────┴────────────────────────┐
│      APScheduler Service                │
│  (Fetches data every 5 minutes          │
│   from Yahoo Finance)                   │
└─────────────────────────────────────────┘
```

---

## 📝 Configuration Options

Edit `.env` file:

```bash
# Change default stock
DEFAULT_TICKER=TSLA

# Adjust update frequency (minutes)
UPDATE_INTERVAL_MINUTES=15

# Database settings (default values work)
DB_NAME=momentum_db
DB_USER=momentum_user
DB_PASSWORD=momentum_password
```

After changes:
```bash
docker-compose down
docker-compose up -d
```

---

## 🔍 Advanced Usage

### Access Database Directly
```bash
docker exec -it momentum-postgres psql -U momentum_user -d momentum_db

# Example queries:
SELECT * FROM price_daily WHERE ticker='AAPL' ORDER BY date DESC LIMIT 10;
SELECT * FROM analysis_info WHERE ticker='AAPL' ORDER BY date DESC LIMIT 5;
```

### Check Specific Logs
```bash
# Dashboard logs
docker-compose logs -f dashboard

# Scheduler logs
docker-compose logs -f scheduler

# Database logs
docker-compose logs -f postgres
```

### Restart Individual Services
```bash
docker-compose restart dashboard
docker-compose restart scheduler
docker-compose restart postgres
```

---

## 📦 Local Development (Without Docker)

See main [README.md](README.md) for full local development setup.

---

## 🛠️ TrueNAS Deployment

1. **Upload Files**: Copy entire project to TrueNAS
2. **Configure**: Edit `.env` with production settings
3. **Deploy**: Run `docker-compose up -d`
4. **Persist Data**: Volumes are auto-configured (PostgreSQL 18)
5. **Access**: Use TrueNAS IP:8501

**Note**: Docker Compose automatically pulls PostgreSQL 18 and Python 3.13 images.

---

## 📚 Resources

- **Yahoo Finance**: https://finance.yahoo.com/
- **RSI Indicator**: https://www.investopedia.com/terms/r/rsi.asp
- **MACD Indicator**: https://www.investopedia.com/terms/m/macd.asp
- **Streamlit Docs**: https://docs.streamlit.io/

---

## ⚠️ Important Notes

1. **Not Financial Advice**: This tool is for educational purposes
2. **Placeholder ML**: Current predictions use simple algorithms
3. **API Limits**: Yahoo Finance has rate limits
4. **Data Delay**: Market data may have 15-minute delay
5. **Production ML**: Implement proper models in `models/models.py`
6. **PostgreSQL 18**: Uses latest PostgreSQL features and performance optimizations
7. **Python 3.13**: Optimized with psycopg3 driver for best database performance
8. **Compatibility**: If using external PostgreSQL, ensure version 18+ for full compatibility

---

## 🎉 You're Ready!

Access your dashboard at: **http://localhost:8501**

Happy trading! 📈
