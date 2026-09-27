"""Trade Request model for natural language trade parsing."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TradeRequest:
    """Represents a user's intent to swap tokens, parsed from natural language or structured input."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    input_text: str = ""
    token_in: str = ""
    token_out: str = ""
    amount_in: float = 0.0
    amount_out_min: float = 0.0
    intent: str = ""  # e.g., "low_slippage", "fast_execution", "best_output"
    timestamp: datetime = field(default_factory=datetime.now)
    status: str = "pending"  # pending, processing, completed, failed

    def __post_init__(self):
        """Validate the trade request after initialization."""
        if self.amount_in <= 0:
            raise ValueError("amount_in must be positive")
        # We can add more validation here, e.g., check that token_in and token_out are known tokens
        # but we don't have a token registry in this model. Validation of tokens will happen in the services.
