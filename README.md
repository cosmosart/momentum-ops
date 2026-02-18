# Momentum Ops - Market Analysis Platform

A professional market analysis application built with Python, Streamlit, and PostgreSQL. Features real-time data ingestion, technical analysis (RSI/MACD), and price predictions for stock market analysis.

## Features

- **Real-time Data Ingestion**: Automated data fetching using yfinance and APScheduler
- **Technical Analysis**: RSI and MACD momentum indicators
- **Price Predictions**: Forecasts for 1 day, 1 week, 1 month, and 1 year timeframes
- **Interactive Dashboard**: Streamlit-based UI with multiple analysis tabs
- **PostgreSQL Database**: Persistent storage for price data and analysis results
- **Docker Support**: Ready for TrueNAS and containerized deployment

## Architecture

```
momentum-ops/
├── database/           # Database schema and operations
│   ├── schema.sql     # PostgreSQL table definitions
│   └── db.py          # Database connection and queries
├── ingestion/         # Data fetching and scheduling
│   ├── fetcher.py     # yfinance data fetcher
│   └── scheduler.py   # APScheduler job manager
├── models/            # ML models and analysis
│   └── models.py      # Technical indicators and prediction placeholders
├── dashboard/         # Streamlit UI
│   ├── app.py         # Main dashboard application
│   ├── momentum_tab.py    # RSI/MACD analysis tab
│   └── predictions_tab.py # Predictions tab
├── Dockerfile         # Container definition
├── docker-compose.yml # Multi-container orchestration
└── requirements.txt   # Python dependencies
```

## Database Schema

### Tables

1. **price_realtime**: Real-time intraday price data
   - ticker, timestamp, open, high, low, close, volume

2. **price_daily**: Daily aggregated price data
   - ticker, date, open, high, low, close, adj_close, volume

3. **analysis_info**: Technical indicators and predictions
   - ticker, date, rsi, macd, macd_signal, macd_hist
   - prediction_1d, prediction_1w, prediction_1m, prediction_1y

## Quick Start

### Prerequisites

- Docker and Docker Compose (recommended)
- OR Python 3.11+ and PostgreSQL 15+

### Option 1: Docker Deployment (Recommended)

1. Clone the repository:
```bash
git clone https://github.com/cosmosart/momentum-ops.git
cd momentum-ops
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your preferred settings
```

3. Start the application:
```bash
docker-compose up -d
```

4. Access the dashboard:
   - Open browser to http://localhost:8501

5. Stop the application:
```bash
docker-compose down
```

### Option 2: Local Development

1. Clone and setup:
```bash
git clone https://github.com/cosmosart/momentum-ops.git
cd momentum-ops
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Setup PostgreSQL database:
```bash
# Create database and user
psql -U postgres
CREATE DATABASE momentum_db;
CREATE USER momentum_user WITH PASSWORD 'momentum_password';
GRANT ALL PRIVILEGES ON DATABASE momentum_db TO momentum_user;
\q

# Initialize schema
psql -U momentum_user -d momentum_db -f database/schema.sql
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

4. Run data scheduler (in one terminal):
```bash
python -c "from ingestion.scheduler import DataScheduler; import time; scheduler = DataScheduler(); scheduler.start(); time.sleep(999999)"
```

5. Run dashboard (in another terminal):
```bash
streamlit run dashboard/app.py
```

6. Access at http://localhost:8501

## Configuration

Edit `.env` file to customize:

```bash
# Database Configuration
DB_HOST=postgres           # Use 'localhost' for local dev
DB_PORT=5432
DB_NAME=momentum_db
DB_USER=momentum_user
DB_PASSWORD=momentum_password

# Application Configuration
DEFAULT_TICKER=AAPL              # Default stock ticker
UPDATE_INTERVAL_MINUTES=5        # Data update frequency

# Scheduler Configuration
SCHEDULER_TIMEZONE=UTC
```

## Usage

### Dashboard Features

1. **Momentum Analysis Tab**
   - View candlestick price charts
   - RSI indicator with overbought/oversold signals
   - MACD indicator with signal line and histogram
   - Automated signal interpretation

2. **Predictions Tab**
   - Price forecasts for multiple timeframes
   - Visual representation of predictions
   - Historical price trends

### Supported Tickers

Any valid stock ticker from Yahoo Finance (e.g., AAPL, GOOGL, MSFT, TSLA, etc.)

## Development

### Adding New Indicators

Edit `models/models.py` and add your indicator calculation to `calculate_indicators()`.

### Implementing ML Models

Replace placeholder functions in `models/models.py`:
- `train_model()`: Implement model training (LSTM, ARIMA, Prophet)
- `predict_with_model()`: Implement model inference
- `generate_predictions()`: Update with trained model predictions

### Adding New Dashboard Tabs

1. Create new tab file in `dashboard/`
2. Import and render in `dashboard/app.py`

## TrueNAS Deployment

1. Copy project to TrueNAS server
2. Use the included `docker-compose.yml`
3. Configure persistent volumes for data retention
4. Set appropriate network settings
5. Use TrueNAS Apps or run via command line:
```bash
docker-compose up -d
```

## Technical Stack

- **Backend**: Python 3.11
- **Database**: PostgreSQL 15
- **Data Source**: yfinance
- **Scheduling**: APScheduler
- **UI**: Streamlit
- **Analysis**: pandas, ta (technical analysis)
- **Visualization**: Plotly
- **Containerization**: Docker & Docker Compose

## Dependencies

See `requirements.txt` for full list. Key packages:
- streamlit
- pandas, numpy
- psycopg2-binary, sqlalchemy
- yfinance
- APScheduler
- ta (technical analysis)
- plotly
- scikit-learn

## Monitoring

### Docker Logs

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f dashboard
docker-compose logs -f scheduler
docker-compose logs -f postgres
```

### Database Connection

```bash
# Connect to PostgreSQL container
docker exec -it momentum-postgres psql -U momentum_user -d momentum_db

# Check data
SELECT * FROM price_daily ORDER BY date DESC LIMIT 10;
SELECT * FROM analysis_info ORDER BY date DESC LIMIT 10;
```

## Troubleshooting

### Dashboard shows "No data available"

- Wait a few minutes for initial data ingestion
- Check scheduler logs: `docker-compose logs scheduler`
- Verify internet connection for yfinance API

### Database connection failed

- Ensure PostgreSQL container is running
- Verify credentials in `.env` file match docker-compose.yml
- Check network connectivity between containers

### Ticker not found

- Verify ticker symbol is valid on Yahoo Finance
- Check for typos in ticker input
- Some tickers may not have intraday data available

## License

See [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and questions, please open an issue on GitHub.

## Roadmap

- [ ] Implement production-grade ML models (LSTM, Prophet)
- [ ] Add more technical indicators (Bollinger Bands, Stochastic)
- [ ] Support for cryptocurrency data
- [ ] Portfolio tracking and analysis
- [ ] Alert system for price movements
- [ ] REST API for programmatic access
- [ ] User authentication and multi-user support