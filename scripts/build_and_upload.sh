#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------------------
# build_and_upload.sh — Build ONE production container, push to Docker Hub,
#                       and sync all model artifacts to the remote server.
#
# The single container loads ALL strategy models (conservative, active,
# experimental) from the shared model_artifacts/ volume and runs multi-model
# inference in a single pass.
#
# Usage:
#   ./scripts/build_and_upload.sh              # full build + push + deploy
#   ./scripts/build_and_upload.sh --no-build   # skip build, just upload models
#   ./scripts/build_and_upload.sh --models     # upload model artifacts only
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load env vars from .env (if present)
[[ -f "$PROJECT_ROOT/.env" ]] && set -a && source "$PROJECT_ROOT/.env" && set +a

DEPLOY_USER="${DEPLOY_USER:?Set DEPLOY_USER in .env}"
DEPLOY_HOST="${DEPLOY_HOST:?Set DEPLOY_HOST in .env}"
REMOTE_APP_DIR="${DEPLOY_APP_DIR:?Set DEPLOY_APP_DIR in .env}"
REMOTE_MODEL_DIR="${DEPLOY_MODEL_DIR:?Set DEPLOY_MODEL_DIR in .env}"

REGISTRY="cosmosart"
IMAGE_NAME="momentum-ops"
IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"

# Colours
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"; }
ok()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
fail() { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
SKIP_BUILD=false
MODELS_ONLY=false

for arg in "$@"; do
    case "$arg" in
        --no-build)  SKIP_BUILD=true ;;
        --models)    MODELS_ONLY=true ;;
        --help|-h)
            echo "Usage: $0 [--no-build] [--models] [--help]"
            echo ""
            echo "  --no-build   Skip Docker build, upload existing image"
            echo "  --models     Upload model artifacts only (no image/restart)"
            echo "  --help       Show this message"
            echo ""
            echo "Model artifacts expected in model_artifacts/:"
            echo "  xgboost_direction_conservative.json  xgboost_threshold_conservative.json"
            echo "  xgboost_direction_active.json        xgboost_threshold_active.json"
            echo "  xgboost_direction_experimental.json   xgboost_threshold_experimental.json"
            echo "  (plus per-horizon variants: _conservative_1d, _active_1w, etc.)"
            exit 0
            ;;
        *) fail "Unknown flag: $arg" ;;
    esac
done

cd "$PROJECT_ROOT"

# ---------------------------------------------------------------------------
# Models-only shortcut
# ---------------------------------------------------------------------------
if $MODELS_ONLY; then
    log "Uploading model artifacts to ${DEPLOY_HOST}:${REMOTE_MODEL_DIR}/"
    if [[ ! -d model_artifacts ]] || [[ -z "$(ls model_artifacts/xgboost_*.json 2>/dev/null)" ]]; then
        fail "No model artifacts found in model_artifacts/. Run train_local.py first."
    fi
    rsync -avz --progress model_artifacts/xgboost_*.json \
        "${DEPLOY_USER}@${DEPLOY_HOST}:${REMOTE_MODEL_DIR}/"
    ok "Model artifacts uploaded. Scheduler will pick them up on next cycle."
    exit 0
fi

# ---------------------------------------------------------------------------
# Step 1: Validate
# ---------------------------------------------------------------------------
log "Validating project..."

python -m py_compile models/models.py
python -m py_compile models/features.py
python -m py_compile ingestion/scheduler.py
python -m py_compile run_scheduler.py
python -m py_compile dashboard/app.py
ok "Python compilation checks passed"

if [[ ! -f docker-compose.yml ]]; then
    fail "docker-compose.yml not found"
fi

# ---------------------------------------------------------------------------
# Step 2: Build Docker images
# ---------------------------------------------------------------------------
if ! $SKIP_BUILD; then
    log "Building dashboard image (${REGISTRY}/${IMAGE_NAME}:latest)..."
    docker build \
        -t "${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}" \
        -t "${REGISTRY}/${IMAGE_NAME}:latest" \
        -f Dockerfile \
        .
    ok "Dashboard image built: ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"

    log "Building scheduler image (${REGISTRY}/${IMAGE_NAME}:scheduler)..."
    docker build \
        -t "${REGISTRY}/${IMAGE_NAME}:scheduler" \
        -f Dockerfile.scheduler \
        .
    ok "Scheduler image built: ${REGISTRY}/${IMAGE_NAME}:scheduler"

    # ---------------------------------------------------------------------------
    # Step 3: Push to Docker Hub
    # ---------------------------------------------------------------------------
    log "Pushing images to Docker Hub..."
    docker push "${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    docker push "${REGISTRY}/${IMAGE_NAME}:latest"
    docker push "${REGISTRY}/${IMAGE_NAME}:scheduler"
    ok "All images pushed to Docker Hub"
else
    ok "Skipping build — will pull existing images on remote"
fi

# ---------------------------------------------------------------------------
# Step 4: Upload model artifacts (all strategies in one directory)
# ---------------------------------------------------------------------------
if [[ -d model_artifacts ]] && [[ -n "$(ls model_artifacts/xgboost_*.json 2>/dev/null)" ]]; then
    log "Uploading model artifacts..."
    rsync -avz --progress model_artifacts/xgboost_*.json \
        "${DEPLOY_USER}@${DEPLOY_HOST}:${REMOTE_MODEL_DIR}/"
    ok "Model artifacts uploaded"
    echo ""
    log "Artifacts synced:"
    ls -1 model_artifacts/xgboost_*.json | sed 's|.*/|    |'
else
    warn "No model artifacts found — skipping (run train_local.py to generate)"
fi
