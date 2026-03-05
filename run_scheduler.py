"""
Legacy scheduler entry point — DEPRECATED.

This file previously launched the APScheduler-based DataScheduler.
All orchestration has been migrated to Prefect flows in ``ingestion/flows.py``.

To start the new orchestration:
    prefect deploy --all
    prefect worker start -p proxmox-local-pool

Or run a one-shot ingestion:
    python -m ingestion.flows

This shim remains so that existing scripts or CI that invoke
``python run_scheduler.py`` receive a clear migration message.
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Print migration notice and run a one-shot daily batch flow."""
    logger.warning(
        "run_scheduler.py is DEPRECATED. "
        "Orchestration has moved to Prefect — see ingestion/flows.py and prefect.yaml."
    )
    logger.info("Running one-shot daily_batch_flow for backward compatibility...")

    from ingestion.flows import daily_batch_flow  # noqa: WPS433 (late import OK)

    daily_batch_flow()


if __name__ == "__main__":
    main()