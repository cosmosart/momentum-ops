#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# bootstrap_prefect.sh — One-time setup after Prefect server is running
#
# Usage:
#   PREFECT_API_URL=http://localhost:4200/api ./scripts/bootstrap_prefect.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PREFECT_API_URL="${PREFECT_API_URL:-http://localhost:4200/api}"
export PREFECT_API_URL

echo "⏳ Waiting for Prefect server at ${PREFECT_API_URL} ..."

for i in $(seq 1 30); do
  if python -c "import httpx; httpx.get('${PREFECT_API_URL}/health').raise_for_status()" 2>/dev/null; then
    echo "✅ Prefect server is healthy."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "❌ Prefect server did not become healthy within 30 attempts."
    exit 1
  fi
  sleep 2
done

echo ""
echo "── Creating work pool: proxmox-local-pool ──"
prefect work-pool create proxmox-local-pool --type process --overwrite 2>/dev/null \
  && echo "✅ Work pool created." \
  || echo "ℹ️  Work pool already exists."

echo ""
echo "── Registering deployments from prefect.yaml ──"
prefect deploy --all
echo "✅ Deployments registered."

echo ""
echo "── Summary ──"
prefect work-pool ls
echo ""
prefect deployment ls
echo ""
echo "🚀 Bootstrap complete. Start a worker with:"
echo "   prefect worker start --pool proxmox-local-pool --type process"
