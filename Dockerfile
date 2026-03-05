# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Streamlit dashboard (root-level convenience)
#
# Canonical Dockerfiles live in infrastructure/docker/.  This root-level
# file is kept for backward compatibility with existing CI/CD pipelines
# and ``docker build .`` workflows.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /opt/momentum-ops

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies (dashboard group only)
COPY pyproject.toml ./
RUN uv pip install --system ".[dashboard]"

# Copy application code
COPY shared/ shared/
COPY dashboard/ dashboard/
COPY models/ models/
COPY model_artifacts/ model_artifacts/

# Create a non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /opt/momentum-ops

USER appuser

# Expose Streamlit port
EXPOSE 8501

# Default command runs the dashboard
CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
