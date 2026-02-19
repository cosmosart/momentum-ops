#!/bin/bash
set -e

echo "Starting momentum-ops scheduler..."
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo "Environment:"
env | grep -E "DB_|SCHEDULER_|UPDATE_|DEFAULT_" || true

exec python -u run_scheduler.py
