"""Concentrated liquidity monitoring and PnL calculations for Orca/Raydium."""

import logging
import math
from typing import Dict, List, Optional

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey as PublicKey

from ..models import LiquidityPosition
from ..state import add_position
from ..utils import async_retry

logger = logging.getLogger(__name__)

def tick_to_price(tick: int) -> float:
    """Convert tick to price (simplified)."""
    return 1.0001 ** tick

def price_to_tick(price: float) -> int:
    """Convert price to tick."""
    return int(math.log(price, 1.0001))

@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_account_info(account: str, rpc_url: str) -> Dict:
    """Fetch account data from Solana RPC."""
    client = AsyncClient(rpc_url)
    try:
        resp = await client.get_account_info(PublicKey.from_string(account), encoding='json')
        return resp
    finally:
        await client.close()

@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_transaction(tx_hash: str, rpc_url: str) -> Dict:
    """Fetch transaction details."""
    client = AsyncClient(rpc_url)
    try:
        resp = await client.get_transaction(tx_hash, encoding='json', commitment='confirmed')
        return resp
    finally:
        await client.close()

async def fetch_orca_whirlpool_position(position_id: str, rpc_url: str) -> Optional[LiquidityPosition]:
    """
    Fetch a specific Orca Whirlpool position from RPC.

    Not implemented: on-chain Whirlpool account decoding is Phase 1 scope.
    Returns None (explicit unavailable) instead of the mock position this
    function used to fabricate.
    """
    logger.warning(
        f"fetch_orca_whirlpool_position({position_id}): on-chain ingestion "
        "not implemented (Phase 1) — returning None, not mock data."
    )
    return None


async def fetch_all_positions(owner: str, rpc_url: str, pool_ids: List[str]) -> List[LiquidityPosition]:
    """
    Fetch all positions for a given owner across multiple pools.

    Not implemented: the previous version returned fabricated positions.
    Until Phase 1 on-chain ingestion lands, this returns an empty list and
    the UI shows "no position ingestion connected".
    """
    logger.warning(
        "fetch_all_positions: no real position ingestion implemented yet "
        "(Phase 1). Returning empty list — no mock positions."
    )
    return []

def compute_impermanent_loss(price_current: float, price_entry: float) -> float:
    """Compute impermanent loss percentage."""
    if price_entry == 0:
        return 0.0
    ratio = price_current / price_entry
    il = 2 * math.sqrt(ratio) / (1 + ratio) - 1
    return abs(il) * 100  # as percentage (absolute value)

def compute_net_yield(fees_earned: float, impermanent_loss: float, liquidity: float, time_days: float = 30) -> float:
    """Compute net yield annualized percentage."""
    if liquidity == 0 or time_days == 0:
        return 0.0
    net = fees_earned - impermanent_loss
    annualized = (net / liquidity) * (365 / time_days) * 100
    return annualized

def check_boundary(current_tick: int, tick_lower: int, tick_upper: int) -> bool:
    """Check if position is out of range."""
    return current_tick < tick_lower or current_tick > tick_upper

async def update_positions(owner: str, rpc_url: str, pool_ids: List[str]) -> List[LiquidityPosition]:
    """Fetch and update positions in global state."""
    positions = await fetch_all_positions(owner, rpc_url, pool_ids)
    for pos in positions:
        add_position(pos)
    return positions
