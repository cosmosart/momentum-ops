# ─────────────────────────────────────────────────────────────────────────────
# infrastructure/deploy/README.md
#
# Production deployment is split across 4 independent hosts/VMs.
# Each host runs its own docker-compose file with a shared .env.
#
# ┌──────────────────────────────────────────────────────────────────────────┐
# │  Host              │ Compose file           │ Ports                     │
# ├──────────────────────────────────────────────────────────────────────────┤
# │  db-server         │ docker-compose.db.yml   │ 5432                     │
# │  prefect-server    │ docker-compose.prefect.yml │ 4200, 5433           │
# │  dashboard-server  │ docker-compose.dashboard.yml │ 8501               │
# │  ml-server         │ docker-compose.ml.yml   │ (none — manual runs)     │
# └──────────────────────────────────────────────────────────────────────────┘
#
# Startup order:
#   1. db-server        — App PostgreSQL must be up first
#   2. prefect-server   — Prefect API + its own Postgres
#   3. dashboard-server — Streamlit connects to db-server
#   4. ml-server        — Manual ad-hoc training, connects to db-server
#
# After deploying:
#   1. Copy .env.template → .env on each host, fill in IPs/passwords
#   2. On prefect-server: run bootstrap_prefect.sh to create work pool
#   3. On prefect-server: start the ingestion worker
# ─────────────────────────────────────────────────────────────────────────────
