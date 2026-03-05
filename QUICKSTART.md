# Quick Start Guide — Momentum Ops

## Prerequisites

- **Docker & Docker Compose** (recommended)
- **OR** Python 3.12+ with [`uv`](https://docs.astral.sh/uv/) and PostgreSQL 18+

---

## Fastest Way to Get Started (Docker)

```bash
git clone https://github.com/cosmosart/momentum-ops.git
cd momentum-ops
cp .env.example .env          # edit DEFAULT_TICKER, MODEL_ARTIFACTS_HOST_PATH, etc.
docker compose -f infrastructure/docker-compose.yml up -d
```

Open **http://localhost:8501** — the Home page will load immediately.
Prefect flows begin executing as soon as the worker container starts.

```bash
docker compose -f infrastructure/docker-compose.yml logs -f worker     # watch ingestion logs
docker compose -f infrastructure/docker-compose.yml down               # stop
```

---

## Local Development (uv)

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install all extras
git clone https://github.com/cosmosart/momentum-ops.git
cd momentum-ops
uv pip install -e ".[ingestion,ml,dashboard,dev]"

# Ensure Postgres is running, then apply the schema
python -c "from shared.database import execute_ddl; execute_ddl('infrastructure/ddl/baseline.sql')"

# Deploy Prefect flows (requires a running Prefect server)
prefect deploy --all

# Start a local Prefect worker
prefect worker start -p proxmox-local-pool

# Start the dashboard (separate terminal)
streamlit run dashboard/app.py
```

> **Tip:** Install only the extras you need. For example, `uv pip install -e ".[dashboard]"` is
> enough to run the Streamlit dashboard if ingestion happens elsewhere.

---

## Dashboard Pages

### Home
- Overview of the system and quick links to all pages.

### 🎯 Directional Outlook
- **XGBoost probability gauge** for the selected model
- **TreeSHAP bar chart** — top feature drivers (green = bullish, red = bearish)
- **Current Signal Values** — RSI, MACD, Bollinger Bands
- **All Models Overview** — mini gauges for all four models

### 📊 Momentum Analysis
- **Candlestick chart** — recent price action
- **RSI (14)** — overbought (>70) / oversold (<30) zones
- **MACD (12/26/9)** — signal line crossovers and histogram

### 🤖 AI Advisor
- Generates a structured Markdown prompt for ChatGPT / Gemini / Claude
- Includes quantitative data, all 4 model probabilities, SHAP tables
- **Multi-language support** — select response language before generating

### ⚙️ Manage Tickers
- Add new tickers (validated against yfinance)
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

## Prefect Deployments

Two flows are defined in `prefect.yaml` and orchestrated by a Prefect worker:

| Deployment | Cron | Timezone | Description |
|------------|------|----------|-------------|
| `krx-realtime` | `*/5 9-15 * * 1-5` | Asia/Tokyo | Realtime + daily during KRX hours |
| `daily-batch` | `0 18 * * *` | Asia/Tokyo | Full ingestion + inference post-market |

Deploy and start:

```bash
prefect deploy --all
prefect worker start -p proxmox-local-pool
```

---

## Configuration

All settings are managed by Pydantic Settings and can be set via `.env` or environment variables:

```bash
# .env
DB_HOST=postgres
DB_PORT=5432
DB_NAME=momentum_db
DB_USER=momentum_user
DB_PASSWORD=momentum_password
DEFAULT_TICKER=AAPL
UPDATE_INTERVAL_MINUTES=5
SCHEDULER_TIMEZONE=UTC
PREFECT_API_URL=http://prefect:4200/api
MODEL_ARTIFACTS_HOST_PATH=/mnt/data/model_artifacts
```

After changes: `docker compose -f infrastructure/docker-compose.yml down && docker compose -f infrastructure/docker-compose.yml up -d`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "No data available" | Wait for the first Prefect flow run, or check `docker compose logs worker` |
| "Database connection failed" | Run `docker compose ps` — all services should be "Up". Check `.env` credentials. |
| Invalid ticker | Ticker is validated against yfinance when added. Verify symbol on finance.yahoo.com |
| Prefect flows not running | Ensure `prefect deploy --all` was run and a worker is polling `proxmox-local-pool` |

---

## Architecture Overview

```
Streamlit Dashboard (:8501)
  Home / Directional Outlook / Momentum / AI Advisor / Manage Tickers
         |  psycopg_pool (shared/database.py)
         v
PostgreSQL 18
  price_daily / analysis_info (4 prob + 4 JSONB SHAP) / tickers
         ^
         |
Prefect Worker (ingestion/flows.py)
  krx_realtime_flow / daily_batch_flow
  yfinance -> features.py -> FourModelPredictor -> TreeSHAP -> UPSERT
         ^  NFS bind mount
         |
model_artifacts/ (XGBoost JSON + threshold sidecars)
  Written by train_local.py on GPU workstation
```

---

## Advanced: Training Models

```bash
# Install ML extras
uv pip install -e ".[ml]"

# On training workstation (GPU)
python scripts/train_local.py --models active_1w --tune

# Deploy artifacts to TrueNAS
./scripts/deploy.sh
```

See [docs/architecture/current_state.md](docs/architecture/current_state.md) for full design rationale.

---

Access your dashboard at: **http://localhost:8501**
