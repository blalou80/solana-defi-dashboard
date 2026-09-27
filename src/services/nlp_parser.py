"""Natural Language Parser for trade requests."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedTradeRequest:
    """Parsed components of a natural language trade request."""
    token_in: str
    token_out: str
    amount_in: float
    intent: str  # low_slippage, fast_execution, best_output
    confidence: float = 1.0


class NaturalLanguageParser:
    """Parses natural language trade requests into structured data."""

    def __init__(self):
        # Common Solana token symbols and their mint addresses (for mapping)
        # In a real implementation, we might fetch this from a token registry.
        self.token_map = {
            "SOL": "So11111111111111111111111111111111111111112",
            "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
            "BONK": "Bonk1E9P9G5fi8U8i7f6c5j4h3g2f1e0d9c8b7a6",
            # Add more as needed
        }
        # Reverse mapping for display
        self.reverse_token_map = {v: k for k, v in self.token_map.items()}

        # Patterns for intents
        self.intent_patterns = {
            "low_slippage": [
                r"low\s+slippage",
                r"minimize\s+slippage",
                r"best\s+price",
                r"optimal\s+execution",
            ],
            "fast_execution": [
                r"fast",
                r"quick",
                r"instant",
                r"immediate",
            ],
            "best_output": [
                r"more\s+out",
                r"max\s+output",
                r"highest\s+return",
            ],
        }

        # Regex for extracting trade request
        # Example: "Swap 5 SOL for USDC with low slippage"
        self.trade_pattern = re.compile(
            r"""
            (?P<action>swap|trade|exchange)   # Action word
            \s+
            (?P<amount>[\d.]+)               # Amount (numeric)
            \s+
            (?P<token_in>[A-Za-z]+)          # Input token symbol
            \s+
            for\s+
            (?P<token_out>[A-Za-z]+)         # Output token symbol
            (?:\s+
                with\s+
                (?P<intent>[a-zA-Z\s]+))?    # Optional intent
            """,
            re.VERBOSE | re.IGNORECASE,
        )

    def parse(self, text: str) -> Optional[ParsedTradeRequest]:
        """Parse a natural language trade request.

        Args:
            text: The user's input text.

        Returns:
            ParsedTradeRequest if successful, None otherwise.
        """
        match = self.trade_pattern.search(text.strip())
        if not match:
            return None

        amount = float(match.group("amount"))
        token_in = match.group("token_in").upper()
        token_out = match.group("token_out").upper()
        intent_text = match.group("intent")

        # Validate tokens
        if token_in not in self.token_map or token_out not in self.token_map:
            return None

        # Determine intent
        intent = "best_output"  # default
        confidence = 0.5
        if intent_text:
            intent_text_lower = intent_text.lower().strip()
            for intent_key, patterns in self.intent_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, intent_text_lower):
                        intent = intent_key
                        confidence = 0.9
                        break
                if intent != "best_output":
                    break

        return ParsedTradeRequest(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount,
            intent=intent,
            confidence=confidence,
        )


# Example usage
if __name__ == "__main__":
    parser = NaturalLanguageParser()
    examples = [
        "Swap 5 SOL for USDC with low slippage",
        "Trade 10 SOL for USDT fast",
        "Exchange 1.5 SOL for USDC to get more out",
        "I want to swap 100 SOL for USDC",
    ]
    for example in examples:
        result = parser.parse(example)
        print(f"Input: {example}")
        print(f"Parsed: {result}\n")
