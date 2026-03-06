# Momentum Ops — Market Analysis Platform

A production-grade stock momentum prediction monorepo built with Python 3.12,
Streamlit, XGBoost, PostgreSQL 18, and Prefect. Features domain-driven
architecture, automated data ingestion via Prefect flows, technical analysis
(RSI, MACD, Bollinger Bands, ATR), four targeted XGBoost directional-
probability models with TreeSHAP explainability, an AI Advisory prompt
generator, and a Streamlit multipage dashboard — orchestrated via Docker
Compose on Proxmox / TrueNAS SCALE.

## Features

- **Prefect Orchestration**: Two scheduled flows replace legacy APScheduler — KRX realtime (5-min, M-F 09:00–15:30 JST) and Daily Batch (18:00 JST)
- **Domain-Driven Monorepo**: `shared/`, `ingestion/`, `models/`, `dashboard/` with a PEP 621 `pyproject.toml` managed by `uv`
- **Technical Analysis**: RSI (14), MACD (12/26/9), Bollinger Bands (20, 2), ATR (14), rolling volatility, lagged log-returns
- **Four XGBoost Directional Models**: Single-pass feature engineering → 4 concurrent `predict_proba` calls
  - ⚡ Active 1-Week (1.5 % hurdle)
  - 🛡️ Conservative 1-Month (3.0 % hurdle)
  - 🛡️ Conservative 6-Month (7.5 % hurdle)
  - 🧪 Experimental — Next Business Day (0.5 % hurdle)
- **TreeSHAP Local Explainability**: Per-prediction feature contributions stored as JSONB in PostgreSQL
- **AI Advisory Prompt Generator**: Structured Markdown prompt with quantitative data, SHAP values, and multi-language support — ready to paste into ChatGPT / Gemini / Claude
- **Interactive Dashboard**: Streamlit native multipage routing with Plotly gauges and SHAP bar charts
- **Pydantic Settings**: Centralised `BaseSettings` config with connection pooling (`psycopg_pool`)
- **Decoupled Training**: Optuna Bayesian HPO on local GPU (RTX 3070), model artifacts hot-swapped via NFS
- **PostgreSQL 18**: Persistent storage with UPSERT, JSONB columns, and proper indexing
- **uv Package Manager**: Optional dependency groups (`ingestion`, `ml`, `dashboard`, `dev`) — no monolithic `requirements.txt`

## Architecture

```
momentum-ops/
├── pyproject.toml                  # PEP 621 — uv-managed deps with optional groups
├── prefect.yaml                    # Prefect deployments: krx-realtime + daily-batch
├── docker-compose.yml              # Local dev — all-in-one (postgres, prefect, worker, dashboard)
├── shared/                         # Cross-cutting glue layer
│   ├── config.py                   # Pydantic BaseSettings (DB_URL, API keys, app config)
│   └── database.py                 # psycopg_pool ConnectionPool, get_connection(), check_health()
├── ingestion/                      # Data fetching and Prefect flows
│   ├── fetcher.py                  # DataFetcher — yfinance wrapper for realtime (1m) and daily OHLCV
│   └── flows.py                    # Prefect @flow/@task: fetch_active_tickers, upsert, backfill, inference
├── models/                         # ML models and feature engineering
│   ├── features.py                 # 15 FEATURE_COLUMNS, engineer_features(), make_target()
│   └── models.py                   # FourModelPredictor, DirectionPredictor, TreeSHAP, calculate_indicators()
├── model_artifacts/                # XGBoost JSON weights + threshold sidecars (NFS bind mount)
│   ├── xgboost_{strategy}.json             # 4 model weight files
│   └── xgboost_threshold_{strategy}.json   # 4 F1-optimal threshold sidecars
├── dashboard/                      # Streamlit UI (native multipage routing)
│   ├── app.py                      # Entry point — shared sidebar (ticker selector, DB status), Home page
│   ├── pages/                      # Streamlit auto-discovered pages
│   │   ├── 1_directional_outlook.py
│   │   ├── 2_momentum_analysis.py
│   │   ├── 3_ai_advisor.py
│   │   └── 4_manage_tickers.py
│   ├── momentum_tab.py             # Candlestick + RSI + MACD subplots, SMA/EMA overlays
│   ├── predictions_tab.py          # Directional Outlook — probability gauges, TreeSHAP bar charts
│   ├── ai_advisor_tab.py           # LLM prompt export with indicators + SHAP values
│   ├── prompt_generator.py         # generate_llm_advisory_prompt() — Markdown prompt builder
│   ├── ticker_management_tab.py    # Add/deactivate/reactivate tickers with yfinance validation
│   └── utils.py                    # format_price(), format_price_change(), get_currency_info()
├── infrastructure/                 # Docker, DDL, and production deploy
│   ├── docker/
│   │   ├── Dockerfile.worker       # python:3.12-slim + uv — installs [ingestion], runs Prefect worker
│   │   ├── Dockerfile.dashboard    # python:3.12-slim + uv — installs [dashboard], runs Streamlit
│   │   └── Dockerfile.ml           # python:3.12-slim + uv — installs [ml], ad-hoc training
│   ├── ddl/
│   │   └── baseline.sql            # Unified idempotent schema (5 tables)
│   ├── docker-compose.yml          # DEPRECATED — see root compose or deploy/
│   └── deploy/                     # Production per-host compose files
│       ├── docker-compose.db.yml        # db-server: PostgreSQL 18
│       ├── docker-compose.prefect.yml   # prefect-server: Prefect API + worker
│       ├── docker-compose.dashboard.yml # dashboard-server: Streamlit
│       ├── docker-compose.ml.yml        # ml-server: ad-hoc training
│       └── README.md                    # Startup order and host layout
├── scripts/                        # Training, backfill, and deployment
│   ├── train_local.py              # Optuna Bayesian HPO + XGBoost GPU training
│   ├── backfill_history.py         # Bulk yfinance history download
│   └── deploy.sh                   # rsync model artifacts to TrueNAS via SSH
├── tests/                          # Pytest suite
│   └── test_shared.py              # Config, database, and flow import smoke tests
└── docs/architecture/
    └── current_state.md            # Mermaid architecture diagram + design rationale
```

## Database Schema

### Tables

1. **tickers**: Tracked symbols with active/inactive status
2. **price_realtime**: Real-time intraday price data
3. **price_daily**: Daily OHLCV data
4. **fundamental_daily**: Daily fundamental data
5. **analysis_info**: Technical indicators + 4 probability REAL columns + 4 JSONB feature contribution columns

### analysis_info columns

| Column | Type | Description |
|--------|------|-------------|
| `rsi`, `macd`, `macd_signal`, `macd_hist` | DECIMAL | Technical indicators |
| `bb_upper`, `bb_middle`, `bb_lower` | DECIMAL | Bollinger Bands |
| `prob_active_1w` | REAL | ⚡ 1-week directional probability |
| `prob_conservative_1mo` | REAL | 🛡️ 1-month directional probability |
| `prob_conservative_6mo` | REAL | 🛡️ 6-month directional probability |
| `prob_experimental` | REAL | 🧪 Next-business-day probability |
| `features_active_1w` | JSONB | TreeSHAP contributions (per-model) |
| `features_conservative_1mo` | JSONB | TreeSHAP contributions |
| `features_conservative_6mo` | JSONB | TreeSHAP contributions |
| `features_experimental` | JSONB | TreeSHAP contributions |

## Quick Start

### Prerequisites

- **Docker & Docker Compose** (recommended)
- **OR** Python 3.12+ with [`uv`](https://docs.astral.sh/uv/) and PostgreSQL 18+

### Docker — Local Development (Recommended)

The root `docker-compose.yml` starts all 4 services (PostgreSQL, Prefect, worker, dashboard) on a single machine:

```bash
git clone https://github.com/cosmosart/momentum-ops.git
cd momentum-ops
cp .env.example .env    # edit as needed
docker compose up -d
```

Access the dashboard at **http://localhost:8501** · Prefect UI at **http://localhost:4200**

### Docker — Production (Multi-Host)

Production deploys each concern to its own host/VM using split compose files in `infrastructure/deploy/`:

| Host | Compose file | Service |
|------|-------------|---------|
| db-server | `docker-compose.db.yml` | PostgreSQL 18 (port 5432) |
| prefect-server | `docker-compose.prefect.yml` | Prefect API + ingestion worker (port 4200) |
| dashboard-server | `docker-compose.dashboard.yml` | Streamlit (port 8501) |
| ml-server | `docker-compose.ml.yml` | Ad-hoc training (no exposed ports) |

```bash
# Example: start db-server
cd infrastructure/deploy
cp .env.template .env   # fill in IPs and passwords
docker compose -f docker-compose.db.yml --env-file .env up -d
```

Startup order: **db → prefect → dashboard → ml** (see `infrastructure/deploy/README.md` for details).

### Local Development (uv)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependency groups
uv pip install -e ".[ingestion,ml,dashboard,dev]"

# Deploy Prefect flows (requires a running Prefect server)
prefect deploy --all

# Start a Prefect worker
prefect worker start -p proxmox-local-pool

# Start dashboard (separate terminal)
streamlit run dashboard/app.py
```

## Dashboard Pages

| Page | Description |
|------|-------------|
| 🏠 **Home** | Overview and quick links |
| 🎯 **Directional Outlook** | XGBoost probability gauges, TreeSHAP bar charts, Bollinger/RSI/MACD signal values |
| 📊 **Momentum Analysis** | Candlestick charts, RSI with overbought/oversold zones, MACD with signal line + histogram |
| 🤖 **AI Advisor** | Generate a structured LLM prompt with indicators, SHAP values, and portfolio mandates |
| ⚙️ **Manage Tickers** | Add (with yfinance validation), deactivate, or reactivate tracked symbols |

## Prefect Deployments

| Deployment | Schedule | Description |
|------------|----------|-------------|
| `krx-realtime` | `*/5 9-15 * * 1-5` (Asia/Tokyo) | Realtime + incremental daily during KRX trading hours |
| `daily-batch` | `0 18 * * *` (Asia/Tokyo) | Full ingestion + inference after all markets close |

## Training

Training runs on a local GPU workstation (or the `ml` Docker container), decoupled from production:

```bash
# Train specific models with Optuna HPO (bare-metal)
python scripts/train_local.py --models active_1w conservative_1mo --tune

# Or via the ml container (GPU passthrough optional)
docker compose -f infrastructure/deploy/docker-compose.ml.yml --env-file .env run --rm ml \
  python scripts/train_local.py --models active_1w --tune --tune-trials 200

# Sync artifacts to production host via rsync
./scripts/deploy.sh
```

Model artifacts are hot-swapped via NFS bind mount — no container rebuild required.

## Technical Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| Package Manager | uv (Astral) with PEP 621 `pyproject.toml` |
| Database | PostgreSQL 18 (psycopg 3 + psycopg_pool) |
| Configuration | Pydantic Settings v2 |
| Orchestration | Prefect 3 (replaces APScheduler) |
| ML | XGBoost 2.1+ (GPU `hist`), scikit-learn, Optuna |
| Explainability | Native TreeSHAP (`pred_contribs=True`) |
| Dashboard | Streamlit 1.44+ (native multipage), Plotly |
| Data | yfinance, pandas, ta |
| Deployment | Docker Compose (local + per-host split), Proxmox, NFS |

## Configuration

All settings are managed via environment variables (or `.env` file) and validated by Pydantic:

```bash
# .env — local development (root docker-compose.yml)
DB_HOST=postgres
DB_PORT=5432
DB_NAME=momentum_db
DB_USER=momentum_user
DB_PASSWORD=momentum_password
DEFAULT_TICKER=AAPL
PREFECT_API_URL=http://prefect:4200/api
PREFECT_UI_API_URL=http://localhost:4200/api
MODEL_ARTIFACTS_HOST_PATH=/mnt/data/model_artifacts

# Production only (infrastructure/deploy/*.yml)
# DB_HOST=<db-server IP>            # required on prefect, dashboard, ml hosts
# DEPLOY_USER=<ssh-user>            # for scripts/deploy.sh rsync
# DEPLOY_HOST=<truenas-ip>          # target host for model artifacts
# DEPLOY_MODEL_DIR=/mnt/data/models # remote artifact directory
```

## License

See [LICENSE](LICENSE) file for details.