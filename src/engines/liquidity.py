"""Concentrated liquidity monitoring and PnL calculations for Orca/Raydium."""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import aiohttp
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey as PublicKey
import math

from ..utils import async_retry
from ..models import LiquidityPosition
from ..state import get_state, add_position

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
    This is a stub; actual parsing would depend on Orca's program data.
    """
    logger.info(f"Fetching position {position_id} from {rpc_url}")
    # For MVP, return a mock position.
    mock_position = LiquidityPosition(
        id=position_id,
        pool_id="orca_pool_1",
        owner="mock_owner",
        tick_lower=-100,
        tick_upper=100,
        current_tick=0,
        liquidity=1000.0,
        fees_earned=10.0,
        impermanent_loss=5.0,
        net_yield=20.0
    )
    return mock_position

async def fetch_all_positions(owner: str, rpc_url: str, pool_ids: List[str]) -> List[LiquidityPosition]:
    """
    Fetch all positions for a given owner across multiple pools.
    For MVP, returns a list of mock positions.
    """
    positions = []
    for i, pool_id in enumerate(pool_ids):
        pos = LiquidityPosition(
            id=f"pos_{i}",
            pool_id=pool_id,
            owner=owner,
            tick_lower=-50 + i*10,
            tick_upper=50 + i*10,
            current_tick=0,
            liquidity=500.0 * (i+1),
            fees_earned=2.0 * (i+1),
            impermanent_loss=1.0 * (i+1),
            net_yield=5.0 * (i+1)
        )
        positions.append(pos)
    return positions

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