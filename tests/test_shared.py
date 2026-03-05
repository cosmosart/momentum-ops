"""
Smoke tests for the shared glue layer and Prefect flow definitions.

Run with:
    pytest tests/ -v
"""

from __future__ import annotations

import importlib


class TestConfigLoads:
    """Ensure shared.config can be imported and produces a Settings object."""

    def test_settings_defaults(self) -> None:
        from shared.config import Settings

        s = Settings()
        assert s.db_host == "localhost"
        assert s.db_port == 5432
        assert s.db_name == "momentum_db"
        assert "postgresql://" in s.db_url

    def test_db_url_composition(self) -> None:
        from shared.config import Settings

        s = Settings(
            db_user="u",
            db_password="p",
            db_host="h",
            db_port=1234,
            db_name="d",
        )
        assert s.db_url == "postgresql://u:p@h:1234/d"


class TestFlowsImportable:
    """Verify that Prefect flow modules import without error."""

    def test_import_flows(self) -> None:
        mod = importlib.import_module("ingestion.flows")
        assert hasattr(mod, "krx_realtime_flow")
        assert hasattr(mod, "daily_batch_flow")
        assert hasattr(mod, "fetch_active_tickers")
        assert hasattr(mod, "fetch_yfinance_daily")
        assert hasattr(mod, "upsert_daily_prices")


class TestDatabaseModuleImport:
    """Ensure the database module can be imported (pool is lazy)."""

    def test_import_database(self) -> None:
        mod = importlib.import_module("shared.database")
        assert hasattr(mod, "get_connection")
        assert hasattr(mod, "check_health")
        assert hasattr(mod, "close_pool")
