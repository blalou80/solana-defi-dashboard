"""Orca Whirlpool API client (v2).

Endpoints verified live 2026-09-27:
- GET /v2/solana/pools/{address}          -> real pool state incl. tickCurrentIndex,
                                             tokenA/tokenB {symbol, decimals}, price
- GET /v2/solana/positions/list?provider={wallet} -> {data:{positions:[...],
                                             whirlpools:{}, tokens:[]}} envelope

Positions are parsed defensively: fields we recognize are mapped, anything
missing stays None (rendered as "unavailable"), and nothing is ever
invented. Fee values are raw token amounts reported by Orca for the
position — provenance is documented in METRICS.md.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from ..models import CLPosition
from ..utils import async_retry

logger = logging.getLogger(__name__)

ORCA_API_V2 = "https://api.orca.so/v2/solana"


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_pool(whirlpool_address: str) -> Dict[str, Any]:
    """Live whirlpool state. Raises on non-200/unparseable response."""
    url = f"{ORCA_API_V2}/pools/{whirlpool_address}"
    async with aiohttp.ClientSession() as session, session.get(url) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"Orca pool fetch {resp.status}: {text[:120]}")
        data = await resp.json()
    return data.get("data") or {}


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_provider_positions(provider: str) -> Tuple[List[Dict], Dict]:
    """Raw positions for a provider wallet + the whirlpools map the API
    returns alongside them."""
    url = f"{ORCA_API_V2}/positions/list"
    params = {"provider": provider, "size": 100}
    async with aiohttp.ClientSession() as session, session.get(url, params=params) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"Orca positions fetch {resp.status}: {text[:120]}")
        data = await resp.json()
    payload = data.get("data") or {}
    return payload.get("positions") or [], payload.get("whirlpools") or {}


def _first(d: Dict, *keys, cast=None):
    """First present non-None value among keys, optionally cast."""
    for k in keys:
        if d.get(k) is not None:
            v = d[k]
            return cast(v) if cast else v
    return None


def parse_position(
    raw: Dict[str, Any],
    pools: Optional[Dict[str, Any]] = None,
) -> Optional[CLPosition]:
    """Convert one raw Orca position record into a CLPosition.

    Returns None when the record cannot yield a fully real position
    (unknown address, missing range ticks, or no live pool tick) — a
    position we cannot monitor truthfully is dropped and logged, never
    half-invented.
    """
    pools = pools or {}
    address = _first(raw, "address", "positionAddress", "pubkey")
    whirlpool = _first(raw, "whirlpoolAddress", "whirlpool")
    if not address or not whirlpool:
        logger.warning(f"Unrecognized Orca position record keys: {sorted(raw)[:8]}")
        return None

    pool = pools.get(whirlpool) or {}
    token_a = (pool.get("tokenA") or {}).get("symbol")
    token_b = (pool.get("tokenB") or {}).get("symbol")

    tick_lower = _first(raw, "priceTicksLower", "tickLower", cast=int)
    tick_upper = _first(raw, "priceTicksUpper", "tickUpper", cast=int)
    current_tick = _first(pool, "tickCurrentIndex", "tickCurrent", cast=int)

    if tick_lower is None or tick_upper is None or current_tick is None:
        logger.warning(
            f"Position {address}: missing real ticks "
            f"(lower={tick_lower}, upper={tick_upper}, current={current_tick}) "
            "— dropped, not fabricated."
        )
        return None
    if tick_lower >= tick_upper:
        logger.warning(f"Position {address}: inverted tick range — dropped.")
        return None

    liquidity_raw = _first(raw, "liquidity", cast=float)
    is_in_range = tick_lower <= current_tick <= tick_upper

    return CLPosition(
        position_id=str(address),
        dex_name="Orca",
        pool_address=str(whirlpool),
        token_a=token_a or (_first(raw, "tokenAMint") or "")[:8] or "",
        token_b=token_b or (_first(raw, "tokenBMint") or "")[:8] or "",
        tick_lower=tick_lower,
        tick_upper=tick_upper,
        current_tick=current_tick,
        liquidity=liquidity_raw or 0.0,
        fees_owed_a=_first(raw, "feeOwedA", "feesOwedA", cast=float) or 0.0,
        fees_owed_b=_first(raw, "feeOwedB", "feesOwedB", cast=float) or 0.0,
        is_in_range=is_in_range,
    )


async def fetch_positions_with_live_ticks(provider: str) -> List[CLPosition]:
    """Provider positions enriched with each pool's live current tick.

    The list endpoint may embed whirlpools; pools missing from it are
    fetched individually so every persisted tick is real and current.
    """
    raws, embedded_pools = await get_provider_positions(provider)
    positions: List[CLPosition] = []
    pool_cache: Dict[str, Dict] = dict(embedded_pools)
    for raw in raws:
        whirlpool = _first(raw, "whirlpoolAddress", "whirlpool")
        if whirlpool and whirlpool not in pool_cache:
            try:
                pool_cache[whirlpool] = await get_pool(whirlpool)
            except Exception as e:
                logger.warning(f"Pool {whirlpool} tick fetch failed: {e}")
        pos = parse_position(raw, pool_cache)
        if pos:
            positions.append(pos)
    return positions
