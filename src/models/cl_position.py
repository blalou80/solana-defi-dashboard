"""CL Position model for concentrated liquidity positions."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CLPosition:
    """Represents a concentrated liquidity position with additional analytics."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str = ""  # On-chain position ID from the DEX (e.g., Orca Whirlpool ID)
    dex_name: str = ""  # DEX where position exists (Orca, Raydium)
    pool_address: str = ""  # Address of the liquidity pool
    token_a: str = ""  # First token in the pair
    token_b: str = ""  # Second token in the pair
    tick_lower: int = 0  # Lower tick bound of the position range
    tick_upper: int = 0  # Upper tick bound of the position range
    current_tick: int = 0  # Current tick based on market price
    liquidity: float = 0.0  # Amount of liquidity in the position
    fees_owed_a: float = 0.0  # Accrued fees in token A
    fees_owed_b: float = 0.0  # Accrued fees in token B
    impermanent_loss: float = 0.0  # Current impermanent loss amount/percentage
    projected_il_6h: float = 0.0  # Projected impermanent loss in 6 hours
    projected_il_24h: float = 0.0  # Projected impermanent loss in 24 hours
    projected_il_72h: float = 0.0  # Projected impermanent loss in 72 hours
    suggested_tick_lower: int = 0  # Recommended lower tick for rebalancing
    suggested_tick_upper: int = 0  # Recommended upper tick for rebalancing
    net_yield_estimate: float = 0.0  # Estimated net yield (fees - IL)
    last_updated: datetime = field(default_factory=datetime.now)
    is_in_range: bool = True  # Boolean indicating if position is currently in range
    out_of_range_alert_sent: bool = False  # Flag to prevent alert spam

    def __post_init__(self):
        """Validate the CL position after initialization."""
        if self.tick_lower >= self.tick_upper:
            raise ValueError("tick_lower must be less than tick_upper")
        if self.liquidity < 0:
            raise ValueError("liquidity must be non-negative")
        if self.fees_owed_a < 0 or self.fees_owed_b < 0:
            raise ValueError("fees owed must be non-negative")
        # Note: impermanent loss can be negative in some implementations, but we'll treat it as positive for loss.
        # We'll allow negative values here but note that in analytics we might take absolute value.
        # For simplicity, we'll not validate impermanent loss sign.
