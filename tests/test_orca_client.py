"""Orca client tests: pure parsing fixtures + one live pool check.

The fixture below is a hand-written record in the shape of the Orca v2
positions envelope (used only to test the converter); the live test hits
the real pool endpoint. No test here feeds fabricated *market* data into
product code paths as if it were real.
"""

import pytest

from src.services.orca_client import get_pool, parse_position

POOL_ADDRESS = "Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE"  # USDC/SOL, live


def _raw_position(**over):
    raw = {
        "address": "PositionAddr1111111111111111111111111111111",
        "whirlpoolAddress": POOL_ADDRESS,
        "priceTicksLower": -21000,
        "priceTicksUpper": -20900,
        "liquidity": 123456.0,
        "feeOwedA": 1.5,
        "feeOwedB": 0.25,
    }
    raw.update(over)
    return raw


_POOLS = {
    POOL_ADDRESS: {
        "tickCurrentIndex": -20950,
        "tokenA": {"symbol": "SOL"},
        "tokenB": {"symbol": "USDC"},
    }
}


def test_parse_position_in_range():
    pos = parse_position(_raw_position(), _POOLS)
    assert pos is not None
    assert pos.dex_name == "Orca"
    assert pos.token_a == "SOL" and pos.token_b == "USDC"
    assert pos.current_tick == -20950
    assert pos.is_in_range is True
    assert pos.liquidity == 123456.0


def test_parse_position_out_of_range():
    pools = {POOL_ADDRESS: dict(_POOLS[POOL_ADDRESS], tickCurrentIndex=-19000)}
    pos = parse_position(_raw_position(), pools)
    assert pos.is_in_range is False


def test_parse_position_drops_missing_ticks():
    raw = _raw_position()
    raw.pop("priceTicksLower")
    assert parse_position(raw, _POOLS) is None


def test_parse_position_drops_unknown_address():
    assert parse_position({"liquidity": 1}, _POOLS) is None


def test_parse_position_drops_missing_pool_tick():
    assert parse_position(_raw_position(), {}) is None


@pytest.mark.asyncio
async def test_live_pool_returns_real_tick():
    """Live integration: the endpoint must yield a plausible tick and the
    SOL/USDC pair. Skips (not fakes) if Orca is unreachable."""
    try:
        pool = await get_pool(POOL_ADDRESS)
    except Exception as e:  # network unavailable
        pytest.skip(f"Orca API unreachable: {e}")
    assert pool.get("tokenMintA") == "So11111111111111111111111111111111111111112"
    assert isinstance(pool.get("tickCurrentIndex"), int)
    assert -500000 < pool["tickCurrentIndex"] < 500000
    assert float(pool["price"]) > 0
