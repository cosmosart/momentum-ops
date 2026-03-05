#!/bin/bash
set -e

echo "Starting momentum-ops Prefect worker..."
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo "Environment:"
env | grep -E "DB_|PREFECT_|DEFAULT_" || true

# Register deployments from prefect.yaml then start the worker
prefect deploy --all 2>/dev/null || echo "Deployments already registered or Prefect server unreachable"
exec prefect worker start --pool proxmox-local-pool --type process
