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

TRUENAS_USER="eli"
TRUENAS_IP="172.27.1.45"
TARGET_DIR="/mnt/Main/Apps/momentum_models"

echo "Deploying XGBoost models to TrueNAS..."
rsync -avz --progress ./model_artifacts/xgboost_*.json \
    "${TRUENAS_USER}@${TRUENAS_IP}:${TARGET_DIR}/"

echo ""
echo "Artifacts synced:"
ls -1 model_artifacts/xgboost_*.json | sed 's|.*/|    |'
echo ""
echo "Deployment complete. Scheduler will use new weights on next cycle."