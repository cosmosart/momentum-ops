# Quick Start Guide — Momentum Ops

## Prerequisites

- **Docker & Docker Compose** (recommended)
- **OR** Python 3.13+ and PostgreSQL 18+

---

## Fastest Way to Get Started (Docker)

```bash
git clone https://github.com/cosmosart/momentum-ops.git
cd momentum-ops
cp .env.example .env          # optionally edit DEFAULT_TICKER, UPDATE_INTERVAL_MINUTES
docker-compose up -d
```

Open **http://localhost:8501** — wait 1-2 minutes for initial data ingestion.

```bash
docker-compose logs -f        # watch logs
docker-compose down           # stop
```

---

## Dashboard Pages

### Directional Outlook
- **XGBoost probability gauge** for the selected model (pill selector)
- **TreeSHAP bar chart** — top feature drivers (green = bullish, red = bearish)
- **Current Signal Values** — RSI, MACD, Bollinger Bands
- **All Models Overview** — mini gauges for all four models
- **Signal Interpretation** — regime table + model descriptions

### Momentum Analysis
- **Candlestick chart** — recent price action
- **RSI (14)** — overbought (>70) / oversold (<30) zones
- **MACD (12/26/9)** — signal line crossovers and histogram

### AI Advisor (Gen Prompt)
- Generates a structured Markdown prompt for ChatGPT / Gemini / Claude
- Includes quantitative data, all 4 model probabilities, SHAP tables
- **Multi-language support** — select response language before generating
- Copy-to-clipboard via `st.code` block

### Manage Tickers
- Add new tickers (validated against yfinance — invalid symbols are rejected)
- Deactivate / reactivate tracked symbols
- Historical data is preserved when deactivating

---

## Four XGBoost Models

| Model | Horizon | Hurdle | Use Case |
|-------|---------|--------|----------|
| Active 1-Week | 5 days | 1.5% | Short-term momentum |
| Conservative 1-Month | 21 days | 3.0% | Mid-term holds |
| Conservative 6-Month | 126 days | 7.5% | Long-term structural |
| Experimental (Next Day) | 1 day | 0.5% | Next-business-day direction |

All models share one feature engineering pass (15 features) per ticker per cycle.
TreeSHAP local contributions are computed at inference time and stored as JSONB.

---

## Configuration

Edit `.env`:

```bash
DEFAULT_TICKER=AAPL
UPDATE_INTERVAL_MINUTES=5
DB_HOST=postgres
DB_PORT=5432
DB_NAME=momentum_db
DB_USER=momentum_user
DB_PASSWORD=momentum_password
SCHEDULER_TIMEZONE=UTC
```

After changes: `docker-compose down && docker-compose up -d`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "No data available" | Wait 1-2 min for ingestion, or check `docker-compose logs scheduler` |
| "Database connection failed" | Run `docker-compose ps` — all services should be "Up". Restart with `docker-compose down && docker-compose up -d` |
| Invalid ticker | Ticker is validated against yfinance when added. Verify symbol on finance.yahoo.com |

---

## Architecture Overview

```
Streamlit Dashboard (:8501)
  Directional Outlook / Momentum / AI Advisor / Manage Tickers
         |  psycopg3
         v
PostgreSQL 18
  price_daily / analysis_info (4 prob + 4 JSONB SHAP) / tickers
         ^
         |
APScheduler (5-min cycle)
  yfinance -> features.py -> FourModelPredictor -> TreeSHAP -> UPSERT
         ^  NFS bind mount
         |
model_artifacts/ (XGBoost JSON + threshold sidecars)
  Written by train_local.py on GPU workstation
```

---

## Advanced: Training Models

```bash
# On training workstation (GPU)
python scripts/train_local.py --models active_1w --tune

# Deploy artifacts to TrueNAS
./scripts/deploy.sh
```

See [docs/architecture/current_state.md](docs/architecture/current_state.md) for full design rationale.

---

Access your dashboard at: **http://localhost:8501**
