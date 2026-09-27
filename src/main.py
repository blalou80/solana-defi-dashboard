#!/usr/bin/env python3
"""
Background daemon for Solana DeFi Analytics.
Polls real market data (Solana RPC + Jupiter Price v3) for configured
wallets and persists snapshots to SQLite, which the Streamlit dashboard
reads. No mock data: if a fetch fails, the previous snapshot stands and
the error is logged.
"""
import asyncio
import logging
from typing import List

from src.config import load_config
from src.db import get_connection, list_watchlist, record_positions, record_snapshot
from src.risk.alerts import process_alerts
from src.services.market_data import build_portfolio_balances
from src.services.orca_client import fetch_positions_with_live_ticks
from src.utils import setup_logging

logger = logging.getLogger(__name__)


def resolve_wallets(config, conn) -> List[str]:
    """Wallets to poll = UI watchlist ∪ config.wallet_addresses, deduped,
    order-preserving (watchlist first)."""
    wallets = [w["wallet"] for w in list_watchlist(conn)]
    for w in getattr(config, "wallet_addresses", []) or []:
        if w not in wallets:
            wallets.append(w)
    return wallets


async def tick(config, conn) -> None:
    """One polling cycle: fetch + persist real balances for every wallet."""
    wallets = resolve_wallets(config, conn)
    if not wallets:
        logger.warning(
            "No wallets to poll — add one in the dashboard or set "
            "wallet_addresses in .config.yaml."
        )
        return
    for wallet in wallets:
        try:
            balances = await build_portfolio_balances(
                wallet, config.rpc_endpoint, conn=conn
            )
            snap_id = record_snapshot(
                conn,
                wallet=wallet,
                balances=balances,
                source="solana-rpc+jupiter-price-v3",
            )
            logger.info(f"Snapshot #{snap_id} stored for {wallet[:8]}…")
        except Exception as e:
            # Honest failure: log and keep the last real snapshot.
            logger.error(f"Poll failed for {wallet[:8]}…: {e}", exc_info=True)
        try:
            positions = await fetch_positions_with_live_ticks(wallet)
            if positions:
                stored = record_positions(
                    conn, positions, source="orca-api-v2"
                )
                logger.info(
                    f"Positions stored for {wallet[:8]}…: {stored} "
                    f"({len(positions)} parsed)"
                )
        except Exception as e:
            logger.error(
                f"Orca position fetch failed for {wallet[:8]}…: {e}", exc_info=True
            )


async def background_loop():
    config = load_config()
    conn = get_connection(config.db_path)
    logger.info(
        f"Starting background loop: interval={config.polling_interval_sec}s "
        f"wallets={len(resolve_wallets(config, conn))}"
    )
    while True:
        await tick(config, conn)
        try:
            await process_alerts(conn)
        except Exception as e:
            logger.error(f"Alert processing failed: {e}", exc_info=True)
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
