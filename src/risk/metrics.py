"""Risk metrics: VaR, Sharpe ratio, portfolio aggregation."""

import numpy as np
from typing import List, Optional
import logging
from ..models import Portfolio, LiquidityPosition
from ..state import get_state

logger = logging.getLogger(__name__)

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

def compute_portfolio_metrics(portfolio: Portfolio) -> Portfolio:
    """Given a portfolio, compute total value, exposures, VaR, Sharpe."""
    total_value = 0.0
    exposures = {}
    for pos in portfolio.positions:
        total_value += pos.liquidity
        token = pos.pool_id[:8]
        exposures[token] = exposures.get(token, 0.0) + pos.liquidity

    portfolio.total_value_usd = total_value
    portfolio.token_exposures = exposures

    # Mock VaR and Sharpe using random returns
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 100).tolist()
    portfolio.var_95 = calculate_var(returns, 0.95) * total_value
    portfolio.sharpe_ratio = calculate_sharpe_ratio(returns)

    return portfolio

def update_portfolio_metrics() -> Portfolio:
    """Update portfolio metrics in global state."""
    state = get_state()
    if state.portfolio is None:
        portfolio = Portfolio(positions=state.positions)
    else:
        portfolio = state.portfolio
    compute_portfolio_metrics(portfolio)
    state.portfolio = portfolio
    import datetime
    state.last_update = datetime.datetime.now().isoformat()
    return portfolio