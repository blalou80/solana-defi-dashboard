from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


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
    # None = not enough real history to compute; never a fabricated number.
    # "intraday" metrics come from raw snapshot returns (seconds apart);
    # "daily" metrics from end-of-day rollups (see METRICS.md).
    var_95: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    var_95_daily: Optional[float] = None
    sharpe_daily: Optional[float] = None
    snapshot_count: int = 0  # how many real snapshots back the metrics
    daily_count: int = 0     # how many end-of-day points back daily metrics
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
    threshold_symbol: Optional[str] = None  # e.g. "SOL" for stop_loss
    wallet: Optional[str] = None  # scope: None = all watched wallets
