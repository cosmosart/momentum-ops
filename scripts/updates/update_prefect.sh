#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define variables for cleaner configuration
APP_DIR="/home/eli/app/momentum-ops"
COMPOSE_FILE="${APP_DIR}/infrastructure/deploy/docker-compose.prefect.yml"
# Ensure this points to the exact location of your .env file
ENV_FILE="/mnt/Main/Apps/momentum-ops/ephemeral/.env"

# Execute git pull in the specific target directory
git -C "${APP_DIR}" pull

# Rebuild and start the containers using absolute paths
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --build
docker exec momentum-worker prefect deploy --all
docker exec momentum-worker prefect deployment run 'kis-token-renewal-flow/kis-token-renewal'
docker logs --tail 10 momentum-worker