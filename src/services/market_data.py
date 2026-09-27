"""Real market data: USD prices (Jupiter Price API v3) and wallet balances
(Solana RPC). No value here is ever fabricated — when a source is
unreachable or an asset is unknown, functions return None / omit the row
and the caller must render an explicit unavailable state.

RPC calls use plain JSON-RPC over aiohttp: the public mainnet endpoint
returns error bodies that the typed solana-py client cannot parse, and
balance queries do not need transaction-level deserialization.
"""

import logging
from typing import Dict, List, Optional

import aiohttp

from ..utils import async_retry

logger = logging.getLogger(__name__)

PRICE_API_URL = "https://lite-api.jup.ag/price/v3"

# Known tokens tracked for balances. Mint -> (symbol, decimals).
KNOWN_TOKENS: Dict[str, tuple] = {
    "So11111111111111111111111111111111111111112": ("SOL", 9),
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": ("USDC", 6),
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": ("USDT", 6),
}


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_usd_prices(mints: List[str]) -> Dict[str, Optional[float]]:
    """USD price per mint from Jupiter Price API v3.

    Returns {mint: price}; a mint missing from the API response maps to
    None (unavailable) rather than a made-up number.
    """
    if not mints:
        return {}
    url = f"{PRICE_API_URL}?ids={','.join(mints)}"
    async with aiohttp.ClientSession() as session, session.get(url) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"Price API error {resp.status}: {text[:200]}")
        data = await resp.json()
    return {mint: (data.get(mint) or {}).get("usdPrice") for mint in mints}


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def _rpc_call(session: aiohttp.ClientSession, url: str, method: str, params: List) -> Dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with session.post(url, json=payload) as resp:
        data = await resp.json()
    if "error" in data:
        raise Exception(f"RPC error for {method}: {data['error']}")
    return data["result"]


async def get_wallet_balances(wallet: str, rpc_url: str) -> List[Dict]:
    """Native SOL + known SPL token balances for one wallet, via RPC only.

    Each row: {mint, symbol, amount}. Tokens the wallet does not hold are
    simply absent — never zero-filled with guesses.
    """
    balances: List[Dict] = []
    async with aiohttp.ClientSession() as session:
        result = await _rpc_call(
            session, rpc_url, "getBalance", [wallet, {"commitment": "confirmed"}]
        )
        balances.append(
            {
                "mint": "So11111111111111111111111111111111111111112",
                "symbol": "SOL",
                "amount": result["value"] / (10**9),
            }
        )

        for mint, (symbol, _decimals) in KNOWN_TOKENS.items():
            if mint == "So11111111111111111111111111111111111111112":
                continue  # covered by getBalance above
            result = await _rpc_call(
                session,
                rpc_url,
                "getTokenAccountsByOwner",
                [wallet, {"mint": mint}, {"encoding": "jsonParsed", "commitment": "confirmed"}],
            )
            total = 0.0
            for acc in result.get("value", []):
                info = acc["account"]["data"]["parsed"]["info"]
                total += float(info["tokenAmount"].get("uiAmount") or 0.0)
            if total > 0:
                balances.append({"mint": mint, "symbol": symbol, "amount": total})
    return balances


async def build_portfolio_balances(wallet: str, rpc_url: str) -> List[Dict]:
    """Balances enriched with real USD prices; rows without a price carry
    usd_price=None and usd_value=None."""
    balances = await get_wallet_balances(wallet, rpc_url)
    prices = await get_usd_prices([b["mint"] for b in balances])
    for b in balances:
        price = prices.get(b["mint"])
        b["usd_price"] = price
        b["usd_value"] = None if price is None else b["amount"] * price
    return balances
