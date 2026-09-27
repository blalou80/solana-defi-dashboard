"""Route Comparison model for storing DEX quote comparisons."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RouteComparison:
    """Represents a structured comparison of swap routes across multiple DEXs."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trade_request_id: str = ""
    dex_name: str = ""  # Jupiter, Raydium, Orca
    route_path: str = ""  # e.g., SOL → USDC via Serum
    expected_price: float = 0.0
    price_impact_pct: float = 0.0
    slippage_estimate: float = 0.0
    fill_probability: float = 0.0
    volatility_estimate: float = 0.0
    gas_estimate: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    is_best_route: bool = False
