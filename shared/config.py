"""
Centralised configuration via Pydantic Settings.

All environment variables consumed by momentum-ops are declared here as a
single source of truth.  Values can be set via ``.env`` files, actual
environment variables, or Docker Compose ``environment:`` blocks — Pydantic
Settings handles all three transparently.

Usage
-----
>>> from shared.config import settings
>>> print(settings.db_url)
'postgresql://momentum_user:momentum_password@localhost:5432/momentum_db'
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings sourced from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # silently ignore unexpected env vars
        case_sensitive=False,    # DB_HOST == db_host
    )

    # ── PostgreSQL ────────────────────────────────────────────────────────
    db_host: str = Field(default="localhost", description="Postgres hostname")
    db_port: int = Field(default=5432, description="Postgres port")
    db_name: str = Field(default="momentum_db", description="Postgres database name")
    db_user: str = Field(default="momentum_user", description="Postgres user")
    db_password: str = Field(default="momentum_password", description="Postgres password")

    # ── Computed DSN (read-only) ──────────────────────────────────────────
    @computed_field  # type: ignore[prop-decorator]
    @property
    def db_url(self) -> str:
        """Construct a full ``postgresql://`` DSN from individual components."""
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ── API keys (optional — populated when needed) ───────────────────────
    fmp_api_key: Optional[str] = Field(
        default=None, description="Financial Modeling Prep API key"
    )
    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI API key for advisory features"
    )

    # ── Application behaviour ─────────────────────────────────────────────
    default_ticker: str = Field(
        default="AAPL", description="Fallback ticker when none is specified"
    )
    scheduler_timezone: str = Field(
        default="UTC", description="Timezone for scheduler cron expressions"
    )
    update_interval_minutes: int = Field(
        default=5, ge=1, description="Minutes between ingestion cycles"
    )
    model_artifacts_dir: str = Field(
        default="model_artifacts",
        description="Path to the directory containing trained XGBoost JSON artefacts",
    )
    min_history_rows: int = Field(
        default=200,
        ge=60,
        description="Minimum daily rows required for reliable feature engineering",
    )

    # ── Prefect ───────────────────────────────────────────────────────────
    prefect_api_url: Optional[str] = Field(
        default=None, description="Prefect API endpoint (e.g. http://prefect:4200/api)"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of application settings."""
    return Settings()


# Convenience alias for direct imports:  ``from shared.config import settings``
settings: Settings = get_settings()
