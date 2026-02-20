# Momentum Ops — Implementation Summary

## Overview

Production-grade market analysis system: automated ingestion, four targeted
XGBoost directional-probability models with TreeSHAP explainability, an AI
Advisory prompt generator, and a Streamlit dashboard — deployed as a single
Docker container on TrueNAS SCALE with decoupled GPU training via NFS.

---

## Completed Components

### 1. Database Layer (PostgreSQL 18)

- **schema.sql**: 4 tables (`price_realtime`, `price_daily`, `analysis_info`, `tickers`) with proper indexing
- **db.py**: `Database` class — psycopg 3 with `dict_row`, UPSERT queries (17 parameters), connection management
- **Migrations**:
  - `002_add_multi_horizon_columns.sql` — initial multi-horizon columns
  - `003_add_multi_strategy_columns.sql` — 4 targeted prob columns
  - `004_drop_dead_columns.sql` — removes 20 legacy columns
  - `005_add_feature_contributions.sql` — 4 JSONB columns for TreeSHAP

### 2. Data Ingestion

- **fetcher.py**: yfinance integration — real-time + historical OHLCV
- **scheduler.py**: APScheduler `BackgroundScheduler` (5-min cycle)
  - yfinance fetch → `engineer_features()` (single pass) → `FourModelPredictor.predict_from_ohlcv()` → TreeSHAP contributions → UPSERT to DB
  - Serialises JSONB contributions via `_contrib_json()` helper

### 3. Machine Learning

- **features.py**: Single source of truth — 15 `FEATURE_COLUMNS`, `HORIZONS` dict (5 horizons with hurdle rates), `engineer_features()`, `make_target()`
- **models.py**: `DirectionPredictor` (load, predict, TreeSHAP via `booster.predict(dmatrix, pred_contribs=True)`), `FourModelPredictor` (registry-driven lazy loader), `MODEL_REGISTRY` (4 entries)
  - `predict_from_ohlcv()` returns `tuple[Dict[probs], Dict[contribs]]`
- **train_local.py**: Optuna Bayesian HPO, `TimeSeriesSplit` CV, PR-AUC objective, GPU XGBoost (`tree_method=hist, device=cuda`)
  - `MODEL_DEFAULTS` dict (experimental overfit profile: max_depth=12, n_estimators=2000, no regularization)
  - `TRAINING_PLAN` maps registry keys to horizons
  - F1-optimal threshold exported as sidecar JSON
  - `_derive_threshold_filename()` matches `MODEL_REGISTRY` exactly

### 4. Streamlit Dashboard

- **app.py**: Sidebar navigation (`st.pills`), ticker selector with company names, DB status indicator
- **predictions_tab.py** (Directional Outlook):
  - Model selector (`st.pills`) — 4 models
  - Plotly probability gauge + regime classification
  - TreeSHAP horizontal bar chart (per-model, from JSONB)
  - Current Signal Values (RSI, MACD, Bollinger)
  - All Models Overview (mini gauges)
  - Signal Interpretation expander
- **momentum_tab.py**: Candlestick chart, RSI with zones, MACD with histogram
- **ai_advisor_tab.py**: AI Advisory prompt export
  - Language selector (8 languages: English, Korean, Japanese, Chinese, Spanish, French, German, Portuguese)
  - Generates structured Markdown prompt via `prompt_generator.py`
  - `st.code(..., language="markdown")` with native copy-to-clipboard
- **prompt_generator.py**: `generate_llm_advisory_prompt()` — 4 sections (Request with web search mandate, Quantitative Data table, XGBoost + SHAP tables, Strategic Context), language instruction appended when non-English
- **ticker_management_tab.py**: Add (yfinance-validated), deactivate, reactivate tickers
- **utils.py**: Currency formatting (USD, JPY, KRW, INR, HKD)

### 5. Infrastructure

- **Dockerfile**: Python 3.13 slim, non-root user, health checks
- **docker-compose.yml**: 3-service stack (postgres:18-alpine, scheduler, dashboard), NFS bind-mount for model artifacts
- **build_and_upload.sh**: Docker build + push to `cosmosart/momentum-ops` + rsync
- **deploy.sh**: rsync model artifacts to TrueNAS NFS share

### 6. Documentation

- **README.md**: Comprehensive setup, architecture, schema, training instructions
- **QUICKSTART.md**: Docker quick start, dashboard pages, troubleshooting
- **IMPLEMENTATION.md**: This file
- **docs/architecture/current_state.md**: Mermaid diagram, decoupled compute rationale, multi-model inference, thresholding

---

## Technical Specifications

| Component | Technology |
|-----------|-----------|
| Language | Python 3.13 |
| Database | PostgreSQL 18 (psycopg 3.2+) |
| ML | XGBoost 2.1+ (GPU), scikit-learn, Optuna |
| Explainability | Native TreeSHAP (`pred_contribs=True`) |
| Dashboard | Streamlit 1.44+, Plotly 5.24+ |
| Data | yfinance, pandas 2.2+, ta 0.11+ |
| Scheduling | APScheduler 3.10+ |
| Table Rendering | tabulate 0.9+ |
| Deployment | Docker, Docker Compose, NFS |

---

## Four Production Models

| Model Key | Artifact | Horizon | Hurdle |
|-----------|----------|---------|--------|
| `active_1w` | `xgboost_active_1w.json` | 5 days | 1.5% |
| `conservative_1mo` | `xgboost_conservative_1mo.json` | 21 days | 3.0% |
| `conservative_6mo` | `xgboost_conservative_6mo.json` | 126 days | 7.5% |
| `experimental` | `xgboost_experimental.json` | 1 day | 0.5% |

Each model has a threshold sidecar (`xgboost_threshold_<key>.json`) for F1-optimal binary classification.

---

## Database Schema (post-migration 005)

```sql
analysis_info:
  id, ticker, date,
  rsi, macd, macd_signal, macd_hist,
  bb_upper, bb_middle, bb_lower,
  prob_active_1w, prob_conservative_1mo, prob_conservative_6mo, prob_experimental,
  features_active_1w (JSONB), features_conservative_1mo (JSONB),
  features_conservative_6mo (JSONB), features_experimental (JSONB),
  created_at
  UNIQUE(ticker, date)
```

---

## File Structure

```
momentum-ops/
├── database/
│   ├── schema.sql
│   ├── db.py
│   └── migrations/  (002–005)
├── ingestion/
│   ├── fetcher.py
│   └── scheduler.py
├── models/
│   ├── features.py
│   └── models.py
├── model_artifacts/  (NFS mount — 4 models + threshold sidecars)
├── dashboard/
│   ├── app.py
│   ├── momentum_tab.py
│   ├── predictions_tab.py
│   ├── ai_advisor_tab.py
│   ├── prompt_generator.py
│   ├── ticker_management_tab.py
│   └── utils.py
├── scripts/
│   ├── train_local.py
│   ├── build_and_upload.sh
│   └── deploy.sh
├── docs/architecture/
│   └── current_state.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
├── QUICKSTART.md
└── IMPLEMENTATION.md
```

---

## Deployment

### Docker (Production)
```bash
docker-compose up -d      # Access at :8501
```

### Training (Local GPU)
```bash
python scripts/train_local.py --models active_1w conservative_1mo --tune
./scripts/deploy.sh       # rsync to TrueNAS NFS
```

### Build + Push
```bash
./scripts/build_and_upload.sh
```

---

See [QUICKSTART.md](QUICKSTART.md) for rapid deployment and [docs/architecture/current_state.md](docs/architecture/current_state.md) for design rationale.
