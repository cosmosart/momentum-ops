# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile.ml — ML operations container (manual training & backfill)
#
# Installs core + ml optional-dependency group (xgboost, optuna, shap, etc.)
# No long-running server — used for ad-hoc `docker compose run` sessions.
#
# Build:
#   docker build -f infrastructure/docker/Dockerfile.ml -t momentum-ops:ml .
#
# Run (interactive):
#   docker run --rm -it --gpus all --env-file .env \
#     -v ./model_artifacts:/opt/momentum-ops/model_artifacts \
#     momentum-ops:ml bash
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

LABEL maintainer="Momentum Ops Team"
LABEL description="ML training & operations for momentum-ops"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /opt/momentum-ops

# ── System dependencies (build tools + CUDA support) ─────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
        curl \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

# ── Install uv ───────────────────────────────────────────────────────────
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ── Install core + ml dependencies ───────────────────────────────────────
COPY pyproject.toml README.md ./
RUN uv pip install --system ".[ml]"

# ── Copy full project (training scripts need everything) ─────────────────
COPY shared/ shared/
COPY models/ models/
COPY model_artifacts/ model_artifacts/
COPY scripts/ scripts/
COPY ingestion/ ingestion/
COPY database/ database/

# ── Default: drop into bash for interactive use ──────────────────────────
CMD ["bash"]
