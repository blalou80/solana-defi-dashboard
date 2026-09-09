"""
Shared in-memory state for the application.
Updated by background tasks, read by Streamlit and CLI.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from .models import Portfolio, LiquidityPosition, Alert, Trade

@dataclass
class AppState:
    """Container for all runtime data."""
    portfolio: Optional[Portfolio] = None
    positions: List[LiquidityPosition] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    alerts: List[Alert] = field(default_factory=list)
    pending_alerts: List[Dict] = field(default_factory=list)  # For alert dispatch
    last_update: Optional[str] = None  # ISO timestamp

# Global singleton instance
_state = AppState()

def get_state() -> AppState:
    """Return the global state instance."""
    return _state

def update_state(new_state: AppState):
    """Replace the entire state (for background updates)."""
    global _state
    _state = new_state

def update_portfolio(portfolio: Portfolio):
    """Update portfolio in state."""
    _state.portfolio = portfolio
    _state.last_update = datetime.now().isoformat()

def add_trade(trade: Trade):
    """Add a new trade to history."""
    _state.trades.append(trade)

def add_position(position: LiquidityPosition):
    """Add or update a position (by id)."""
    # Find and replace or append
    for i, p in enumerate(_state.positions):
        if p.id == position.id:
            _state.positions[i] = position
            return
    _state.positions.append(position)

from datetime import datetime  # noqa: E402