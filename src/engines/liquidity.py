"""Concentrated-liquidity math: ticks, impermanent loss, net yield, range.

The RPC fetch helpers and mock-era stubs are gone (position
ingestion lives in services/orca_client.py; receipts in engines/slippage).
What remains is pure, tested math used by risk/metrics and risk/alerts.
"""

import math


def tick_to_price(tick: int) -> float:
    """Convert tick to price (simplified)."""
    return 1.0001 ** tick


def price_to_tick(price: float) -> int:
    """Convert price to tick."""
    return int(math.log(price, 1.0001))


def compute_impermanent_loss(price_current: float, price_entry: float) -> float:
    """Compute impermanent loss percentage."""
    if price_entry == 0:
        return 0.0
    ratio = price_current / price_entry
    il = 2 * math.sqrt(ratio) / (1 + ratio) - 1
    return abs(il) * 100  # as percentage (absolute value)


def compute_net_yield(
    fees_earned: float, impermanent_loss: float, liquidity: float,
    time_days: float = 30,
) -> float:
    """Compute net yield annualized percentage."""
    if liquidity == 0 or time_days == 0:
        return 0.0
    net = fees_earned - impermanent_loss
    annualized = (net / liquidity) * (365 / time_days) * 100
    return annualized


def check_boundary(current_tick: int, tick_lower: int, tick_upper: int) -> bool:
    """Check if position is out of range."""
    return current_tick < tick_lower or current_tick > tick_upper
