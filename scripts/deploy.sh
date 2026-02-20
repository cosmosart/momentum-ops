#!/bin/bash
set -euo pipefail
# ---------------------------------------------------------------------------
# deploy.sh — Sync all strategy model artifacts to TrueNAS inference server
#
# All strategy models (conservative, active, experimental) live in a single
# flat directory.  The container loads whichever xgboost_*.json files it finds.
#
# Usage:
#   ./scripts/deploy.sh                # rsync all model artifacts
# ---------------------------------------------------------------------------

# Load env vars from .env (if present)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
[[ -f "$PROJECT_ROOT/.env" ]] && set -a && source "$PROJECT_ROOT/.env" && set +a

DEPLOY_USER="${DEPLOY_USER:?Set DEPLOY_USER in .env}"
DEPLOY_HOST="${DEPLOY_HOST:?Set DEPLOY_HOST in .env}"
DEPLOY_MODEL_DIR="${DEPLOY_MODEL_DIR:?Set DEPLOY_MODEL_DIR in .env}"

echo "Deploying XGBoost models to ${DEPLOY_HOST}..."
rsync -avz --progress ./model_artifacts/xgboost_*.json \
    "${DEPLOY_USER}@${DEPLOY_HOST}:${DEPLOY_MODEL_DIR}/"

echo ""
echo "Artifacts synced:"
ls -1 model_artifacts/xgboost_*.json | sed 's|.*/|    |'
echo ""
echo "Deployment complete. Scheduler will use new weights on next cycle."