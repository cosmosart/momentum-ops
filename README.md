# Momentum Ops — Market Analysis Platform

A production-grade market analysis system built with Python 3.13, Streamlit,
XGBoost, and PostgreSQL 18. Features automated data ingestion, technical
analysis (RSI, MACD, Bollinger Bands, ATR), four targeted XGBoost directional-
probability models with TreeSHAP explainability, an AI Advisory prompt
generator, and a Streamlit dashboard — all running in a single Docker container
on TrueNAS SCALE.

## Features

- **Real-time Data Ingestion**: Automated OHLCV fetching via yfinance + APScheduler (5-min cycle)
- **Technical Analysis**: RSI (14), MACD (12/26/9), Bollinger Bands (20, 2), ATR (14), rolling volatility, lagged log-returns
- **Four XGBoost Directional Models**: Single-pass feature engineering → 4 concurrent `predict_proba` calls
  - ⚡ Active 1-Week (1.5 % hurdle)
  - 🛡️ Conservative 1-Month (3.0 % hurdle)
  - 🛡️ Conservative 6-Month (7.5 % hurdle)
  - 🧪 Experimental — Next Business Day (0.5 % hurdle)
- **TreeSHAP Local Explainability**: Per-prediction feature contributions stored as JSONB in PostgreSQL
- **AI Advisory Prompt Generator**: Structured Markdown prompt with quantitative data, SHAP values, and multi-language support — ready to paste into ChatGPT / Gemini / Claude
- **Interactive Dashboard**: Streamlit with Plotly gauges, SHAP bar charts, pill-style navigation
- **Ticker Validation**: yfinance-backed validation when adding new tickers
- **Decoupled Training**: Optuna Bayesian HPO on local GPU (RTX 3070), model artifacts hot-swapped via NFS
- **PostgreSQL 18**: Persistent storage with UPSERT, JSONB columns, and proper indexing
- **Docker**: Single container image (`cosmosart/momentum-ops`) for scheduler + dashboard

## Architecture

```
momentum-ops/
├── database/               # PostgreSQL schema, migrations, and CRUD
│   ├── schema.sql          # DDL — 4 tables with indexes
│   ├── db.py               # Database class — UPSERT with 17 params
│   └── migrations/         # Incremental ALTER TABLE scripts
│       ├── 002_add_multi_horizon_columns.sql
│       ├── 003_add_multi_strategy_columns.sql
│       ├── 004_drop_dead_columns.sql
│       └── 005_add_feature_contributions.sql
├── ingestion/              # Data fetching and scheduling
│   ├── fetcher.py          # yfinance OHLCV fetcher
│   └── scheduler.py        # APScheduler → features → 4-model inference → DB
├── models/                 # ML models and feature engineering
│   ├── features.py         # 15 FEATURE_COLUMNS, engineer_features(), make_target()
│   └── models.py           # FourModelPredictor, DirectionPredictor, TreeSHAP
├── model_artifacts/        # XGBoost JSON weights + threshold sidecars (NFS mount)
├── dashboard/              # Streamlit UI
│   ├── app.py              # Entry point — sidebar nav (pills), ticker selector
│   ├── momentum_tab.py     # Candlestick, RSI, MACD charts
│   ├── predictions_tab.py  # Directional Outlook — gauges, SHAP, signal values
│   ├── ai_advisor_tab.py   # AI Advisory prompt export (multi-language)
│   ├── prompt_generator.py # Structured LLM prompt builder
│   ├── ticker_management_tab.py  # Add/deactivate/reactivate tickers
│   └── utils.py            # Currency formatting helpers
├── scripts/                # Training and deployment
│   ├── train_local.py      # Optuna HPO + XGBoost GPU training
│   ├── build_and_upload.sh # Docker build + push + rsync
│   └── deploy.sh           # rsync model artifacts to TrueNAS
├── docs/architecture/      # Technical documentation
│   └── current_state.md    # Mermaid diagram + design rationale
├── Dockerfile              # Python 3.13 slim, single-stage build
├── docker-compose.yml      # 3-service stack (postgres, scheduler, dashboard)
└── requirements.txt        # Python dependencies
```

## Database Schema

### Tables

1. **price_realtime**: Real-time intraday price data
2. **price_daily**: Daily OHLCV data
3. **analysis_info**: Technical indicators + 4 probability REAL columns + 4 JSONB feature contribution columns
4. **tickers**: Tracked symbols with active/inactive status

### analysis_info columns (post-migration 005)

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

- Docker and Docker Compose (recommended)
- OR Python 3.13+ and PostgreSQL 18+

### Docker Deployment (Recommended)

```bash
git clone https://github.com/cosmosart/momentum-ops.git
cd momentum-ops
cp .env.example .env    # edit as needed
docker-compose up -d
```

Access the dashboard at **http://localhost:8501**

### Local Development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Start scheduler
python run_scheduler.py

# Start dashboard (separate terminal)
streamlit run dashboard/app.py
```

## Dashboard Pages

| Page | Description |
|------|-------------|
| 🎯 **Directional Outlook** | XGBoost probability gauges, TreeSHAP bar charts, Bollinger/RSI/MACD signal values, all-models overview |
| 📊 **Momentum Analysis** | Candlestick charts, RSI with overbought/oversold zones, MACD with signal line + histogram |
| 🤖 **AI Advisor** | Generate a structured LLM prompt with indicators, SHAP values, portfolio mandates, and multi-language support |
| ⚙️ **Manage Tickers** | Add (with yfinance validation), deactivate, or reactivate tracked symbols |

## Training

Training runs on a local GPU workstation, decoupled from the production container:

```bash
# Train specific models with Optuna HPO
python scripts/train_local.py --models active_1w conservative_1mo --tune

# Deploy artifacts to TrueNAS via NFS
./scripts/deploy.sh
```

Model artifacts are hot-swapped via NFS bind mount — no container rebuild required.

## Technical Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.13 |
| Database | PostgreSQL 18 (psycopg 3) |
| ML | XGBoost 2.1+ (GPU `hist`), scikit-learn, Optuna |
| Explainability | Native TreeSHAP (`pred_contribs=True`) |
| Dashboard | Streamlit 1.44+, Plotly |
| Data | yfinance, pandas, ta |
| Scheduling | APScheduler (5-min cycle) |
| Deployment | Docker, Docker Compose, NFS |
| Table Rendering | tabulate (pandas `.to_markdown()`) |

## Configuration

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
```

## License

See [LICENSE](LICENSE) file for details.