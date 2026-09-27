#!/usr/bin/env python3
"""
Wrapper script for xyOps to run one Solana DeFi analytics cycle.
Delegates to the daemon's single-tick implementation so both entry
points share exactly the same real-data pipeline (RPC + Jupiter prices
-> SQLite). No mock owners, no in-process-only metrics.
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.config import load_config
from src.db import conn_for
from src.main import tick
from src.risk.alerts import process_alerts
from src.utils import setup_logging

logger = logging.getLogger(__name__)


async def run_analytics_cycle():
    """Run a single analytics update cycle."""
    try:
        config = load_config()
        conn = conn_for(config)
        logger.info("Starting analytics collection cycle")
        await tick(config, conn)
        await process_alerts(conn)
        logger.info("Analytics collection cycle completed successfully")
        return True
    except Exception as e:
        logger.error(f"Error in analytics collection: {e}", exc_info=True)
        return False


def main():
    setup_logging(logging.INFO)
    logger.info("Solana DeFi Analytics wrapper started")
    success = asyncio.run(run_analytics_cycle())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
