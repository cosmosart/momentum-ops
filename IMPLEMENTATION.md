# Momentum Ops — Implementation Summary

## Overview

Production-grade market analysis system: automated ingestion via Prefect flows,
four targeted XGBoost directional-probability models with TreeSHAP explainability,
an AI Advisory prompt generator, and a Streamlit multipage dashboard — deployed as
Docker containers on Proxmox / TrueNAS SCALE with decoupled GPU training via NFS.

---

## Completed Components

### 1. Database Layer (PostgreSQL 18)

- **infrastructure/ddl/baseline.sql**: Unified idempotent DDL — 5 tables (`tickers`, `price_realtime`, `price_daily`, `fundamental_daily`, `analysis_info`) with proper indexing
- **shared/database.py**: `psycopg_pool.ConnectionPool` — thread-safe connection management, `get_connection()` context manager, `check_health()` liveness probe
- **shared/config.py**: Pydantic `BaseSettings` — centralised DB_URL, API keys, and application config
- **Legacy migrations** retained in `database/migrations/` for history

### 2. Data Ingestion (Prefect)

- **ingestion/fetcher.py**: yfinance integration — real-time + historical OHLCV
- **ingestion/flows.py**: Prefect `@flow` / `@task` orchestration (replaces APScheduler)
  - `fetch_active_tickers` — queries `tickers` table for active symbols
  - `fetch_yfinance_daily` / `fetch_yfinance_realtime` — data retrieval with retries + caching
  - `upsert_daily_prices` / `upsert_realtime_price` — batch DB writes
  - `backfill_if_needed` — auto-backfill sparse tickers
  - `run_inference_and_persist` — feature engineering → 4-model XGBoost → TreeSHAP → UPSERT
  - `krx_realtime_flow` — 5-min cycle during KRX hours (M–F 09:00–15:30 JST)
  - `daily_batch_flow` — once daily at 18:00 JST
- **prefect.yaml**: Two deployments targeting `proxmox-local-pool` work pool
- **ingestion/scheduler.py**: Legacy APScheduler module — retained for reference, no longer active

### 3. Machine Learning

- **features.py**: Single source of truth — 15 `FEATURE_COLUMNS`, `HORIZONS` dict (5 horizons with hurdle rates), `engineer_features()`, `make_target()`
- **models.py**: `DirectionPredictor` (load, predict, TreeSHAP via `booster.predict(dmatrix, pred_contribs=True)`), `FourModelPredictor` (registry-driven lazy loader), `MODEL_REGISTRY` (4 entries)
  - `predict_from_ohlcv()` returns `tuple[Dict[probs], Dict[contribs]]`
- **train_local.py**: Optuna Bayesian HPO, `TimeSeriesSplit` CV, PR-AUC objective, GPU XGBoost (`tree_method=hist, device=cuda`)
  - F1-optimal threshold exported as sidecar JSON

### 4. Streamlit Dashboard (Native Multipage)

- **app.py**: Entry point — shared sidebar (ticker selector, DB status indicator via `check_health()`), Home page
- **pages/**: Streamlit native multipage routing (replaces `st.pills` navigation)
  - `1_directional_outlook.py` → `predictions_tab.py`
  - `2_momentum_analysis.py` → `momentum_tab.py`
  - `3_ai_advisor.py` → `ai_advisor_tab.py`
  - `4_manage_tickers.py` → `ticker_management_tab.py`
- **prompt_generator.py**: `generate_llm_advisory_prompt()` — Markdown prompt builder with portfolio mandates
- **utils.py**: Currency formatting (USD, JPY, KRW, INR, HKD)

### 5. Infrastructure

- **infrastructure/docker/Dockerfile.worker**: Python 3.12 slim + uv — installs `[ingestion]` group, starts Prefect worker
- **infrastructure/docker/Dockerfile.dashboard**: Python 3.12 slim + uv — installs `[dashboard]` group, starts Streamlit
- **infrastructure/docker-compose.yml**: 3-service stack (postgres, worker, dashboard), NFS bind-mount for model artifacts
- **pyproject.toml**: PEP 621 with optional dependency groups (`ingestion`, `ml`, `dashboard`, `dev`), managed by uv
- **deploy.sh**: rsync model artifacts to TrueNAS NFS share

### 6. Documentation

- **README.md**: Comprehensive setup, architecture, schema, training instructions
- **QUICKSTART.md**: Docker quick start, Prefect deployments, dashboard pages, troubleshooting
- **IMPLEMENTATION.md**: This file
- **docs/architecture/current_state.md**: Mermaid diagram, decoupled compute rationale, multi-model inference, thresholding

---

## Technical Specifications

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| Package Manager | uv (Astral) with PEP 621 `pyproject.toml` |
| Database | PostgreSQL 18 (psycopg 3.2+ / psycopg_pool) |
| Configuration | Pydantic Settings v2 |
| Orchestration | Prefect 3 |
| ML | XGBoost 2.1+ (GPU), scikit-learn, Optuna |
| Explainability | Native TreeSHAP (`pred_contribs=True`) |
| Dashboard | Streamlit 1.44+ (native multipage), Plotly 5.24+ |
| Data | yfinance, pandas 2.2+, ta 0.11+ |
| Table Rendering | tabulate 0.9+ |
| Deployment | Docker Compose, Proxmox, NFS |

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
├── pyproject.toml              # PEP 621 — uv-managed deps
├── prefect.yaml                # Prefect deployment config
├── shared/
│   ├── config.py               # Pydantic BaseSettings
│   └── database.py             # psycopg_pool ConnectionPool
├── infrastructure/
│   ├── docker/
│   │   ├── Dockerfile.worker
│   │   └── Dockerfile.dashboard
│   ├── ddl/
│   │   └── baseline.sql
│   └── docker-compose.yml
├── ingestion/
│   ├── fetcher.py
│   └── flows.py                # Prefect @flow/@task
├── models/
│   ├── features.py
│   └── models.py
├── model_artifacts/            # NFS mount — 4 models + threshold sidecars
├── dashboard/
│   ├── app.py
│   ├── pages/
│   │   ├── 1_directional_outlook.py
│   │   ├── 2_momentum_analysis.py
│   │   ├── 3_ai_advisor.py
│   │   └── 4_manage_tickers.py
│   ├── momentum_tab.py
│   ├── predictions_tab.py
│   ├── ai_advisor_tab.py
│   ├── prompt_generator.py
│   ├── ticker_management_tab.py
│   └── utils.py
├── scripts/
│   ├── train_local.py
│   └── deploy.sh
├── tests/
│   └── test_shared.py
├── docs/architecture/
│   └── current_state.md
├── Dockerfile                  # Root-level convenience (dashboard)
├── Dockerfile.scheduler        # Deprecated — see Dockerfile.worker
├── docker-compose.yml          # Root-level (points to infra DDL)
├── README.md
├── QUICKSTART.md
└── IMPLEMENTATION.md
```

---

## Deployment

### Docker (Production)
```bash
docker compose -f infrastructure/docker-compose.yml up -d   # Access at :8501
```

### Prefect Flows
```bash
prefect deploy --all                # Register deployments
prefect worker start -p proxmox-local-pool   # Start worker
```

### Training (Local GPU)
```bash
uv pip install -e ".[ml]"
python scripts/train_local.py --models active_1w conservative_1mo --tune
./scripts/deploy.sh               # rsync to TrueNAS NFS
```

---

See [QUICKSTART.md](QUICKSTART.md) for rapid deployment and [docs/architecture/current_state.md](docs/architecture/current_state.md) for design rationale.
