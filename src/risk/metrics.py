"""Risk metrics: VaR, Sharpe ratio, portfolio aggregation.

Phase-0 honesty pass: the old implementation computed VaR/Sharpe from
``np.random.seed(42)`` mock returns. Those are gone. Metrics are now
derived exclusively from persisted portfolio snapshots (src.db); with
insufficient history every derived metric is explicitly ``None`` and the
UI must render "unavailable (n samples)".
"""

import logging
import math
from typing import Dict, List, Optional

import numpy as np

from ..db import (
    daily_value_history,
    latest_snapshot,
    snapshot_value_history,
)
from ..models import Portfolio

logger = logging.getLogger(__name__)

# Minimum snapshots before the intraday metrics are reported at all.
MIN_SAMPLES_VAR = 20
MIN_SAMPLES_SHARPE = 5
# Minimum end-of-day points before daily metrics are reported.
MIN_SAMPLES_DAILY = 5


def calculate_var(values: List[float], confidence: float = 0.95) -> float:
    """Calculate Value at Risk using historical simulation."""
    if not values:
        return 0.0
    sorted_values = np.sort(values)
    index = int((1 - confidence) * len(sorted_values))
    if index >= len(sorted_values):
        index = len(sorted_values) - 1
    return float(sorted_values[index])


def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """Calculate Sharpe ratio from historical returns."""
    if not returns:
        return 0.0
    avg_return = np.mean(returns)
    std_return = np.std(returns)
    if std_return == 0:
        return 0.0
    sharpe = (avg_return - risk_free_rate) / std_return
    return float(sharpe)


def returns_from_values(values: List[float]) -> List[float]:
    """Simple period returns from a value series (empty if < 2 points)."""
    if len(values) < 2:
        return []
    arr = np.asarray(values, dtype=float)
    prev = arr[:-1]
    curr = arr[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = (curr - prev) / np.where(prev == 0, np.nan, prev)
    return [float(x) for x in r if np.isfinite(x)]


def position_impermanent_loss(history: List[Dict]) -> Optional[float]:
    """IL (%) since the position was FIRST OBSERVED, from stored ticks.

    Entry-price proxy: the pool tick of the earliest history row converted
    with tick_to_price; current: the latest row's tick. This is explicitly
    "since first observation" — the daemon cannot know the real on-chain
    entry price, and claiming one would be fabrication. Returns None with
    fewer than 2 observations.
    """
    usable = [h for h in history if h.get("current_tick") is not None]
    if len(usable) < 2:
        return None
    from ..engines.liquidity import tick_to_price

    entry = tick_to_price(usable[0]["current_tick"])
    current = tick_to_price(usable[-1]["current_tick"])
    if entry <= 0:
        return None
    ratio = current / entry
    il = 2 * math.sqrt(ratio) / (1 + ratio) - 1
    return abs(il) * 100


def compute_portfolio_metrics(conn, wallet: str) -> Portfolio:
    """Build a Portfolio strictly from persisted real data.

    total_value_usd / exposures come from the latest snapshot; VaR and
    Sharpe come from the snapshot value history. None = unavailable,
    never a placeholder.
    """
    snap = latest_snapshot(conn, wallet)
    portfolio = Portfolio()
    if snap is None:
        logger.info(f"No snapshots stored for {wallet[:8]}… — portfolio unavailable")
        return portfolio

    portfolio.total_value_usd = float(snap["total_value_usd"])
    exposures: Dict[str, float] = {}
    for b in snap["balances"]:
        key = b.get("symbol") or b["mint"][:8]
        if b.get("usd_value") is not None:
            exposures[key] = exposures.get(key, 0.0) + float(b["usd_value"])
    portfolio.token_exposures = exposures
    portfolio.last_updated = snap["ts"]

    history = snapshot_value_history(conn, wallet)
    if len(history) >= MIN_SAMPLES_VAR:
        returns = returns_from_values(history)
        portfolio.var_95 = abs(calculate_var(returns, 0.95)) * portfolio.total_value_usd
    else:
        portfolio.var_95 = None
    if len(history) >= MIN_SAMPLES_SHARPE:
        returns = returns_from_values(history)
        portfolio.sharpe_ratio = calculate_sharpe_ratio(returns)
    else:
        portfolio.sharpe_ratio = None
    portfolio.snapshot_count = len(history)

    # S3: daily-resolution metrics from the end-of-day rollup, clearly
    # separated from the intraday snapshot metrics above.
    daily = daily_value_history(conn, wallet)
    if len(daily) >= MIN_SAMPLES_DAILY:
        daily_returns = returns_from_values(daily)
        if daily_returns:
            portfolio.var_95_daily = (
                abs(calculate_var(daily_returns, 0.95)) * portfolio.total_value_usd
            )
            portfolio.sharpe_daily = calculate_sharpe_ratio(daily_returns)
    portfolio.daily_count = len(daily)
    return portfolio
