#!/usr/bin/env python3
"""
Background daemon for Solana DeFi Analytics.
Runs polling loop to update positions and portfolio metrics.
"""
import asyncio
import logging
import sys
from src.config import load_config
from src.state import get_state
from src.engines.liquidity import update_positions
from src.risk.metrics import update_portfolio_metrics
from src.risk.alerts import process_alerts
from src.utils import setup_logging

logger = logging.getLogger(__name__)

async def background_loop():
    """Main async loop that polls and updates data."""
    config = load_config()
    logger.info(f"Starting background loop with interval {config.polling_interval_sec}s")
    # For MVP, we'll use a fixed owner and pool list; in production these come from config.
    owner = "mock_owner"  # would be user-provided
    pool_ids = ["orca_pool_1", "orca_pool_2"]  # from config

    while True:
        try:
            logger.debug("Updating positions...")
            positions = await update_positions(owner, config.rpc_endpoint, pool_ids)
            logger.debug(f"Updated {len(positions)} positions")

            # Update portfolio metrics
            update_portfolio_metrics()
            logger.debug("Updated portfolio metrics")

            # Process alerts
            await process_alerts()
            logger.debug("Processed alerts")

        except Exception as e:
            logger.error(f"Error in background loop: {e}", exc_info=True)

        await asyncio.sleep(config.polling_interval_sec)

def main():
    setup_logging(logging.INFO)
    logger.info("Starting Solana DeFi Analytics daemon")
    try:
        asyncio.run(background_loop())
    except KeyboardInterrupt:
        logger.info("Shutting down daemon")

if __name__ == "__main__":
    main()