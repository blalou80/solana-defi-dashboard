from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any

@dataclass
class Trade:
    id: str
    token_in: str
    token_out: str
    amount_in: float
    amount_out_expected: float
    amount_out_realized: Optional[float] = None
    route: str = ""
    price_impact_pct: float = 0.0
    slippage_estimated: float = 0.0
    slippage_realized: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class LiquidityPosition:
    id: str
    pool_id: str
    owner: str
    tick_lower: int
    tick_upper: int
    current_tick: int
    liquidity: float
    fees_earned: float = 0.0
    impermanent_loss: float = 0.0
    net_yield: float = 0.0  # annualized %
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class Portfolio:
    total_value_usd: float = 0.0
    token_exposures: Dict[str, float] = field(default_factory=dict)
    var_95: float = 0.0
    sharpe_ratio: float = 0.0
    positions: List[LiquidityPosition] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class Alert:
    id: str
    type: str  # "stop_loss", "boundary", "anomaly"
    threshold: float
    channel: str  # "telegram", "discord"
    message_template: str
    enabled: bool = True

# Config is already defined in config.py; we re-export from there for convenience.
# We'll import Config from config in other modules.

# Re-export Config from config module if needed.
from src.config import Config  # noqa: F401