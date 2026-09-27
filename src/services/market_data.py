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

# Seed symbol map for alert stop-loss lookups (mint -> (symbol, decimals)).
# The token registry (W2) resolves arbitrary mints; this stays as the
# offline-fast path for the common three.
KNOWN_TOKENS: Dict[str, tuple] = {
    "So11111111111111111111111111111111111111112": ("SOL", 9),
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": ("USDC", 6),
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": ("USDT", 6),
}

# SPL Token + Token-2022 programs — one scan each replaces per-mint queries.
TOKEN_PROGRAMS = (
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
)


async def get_usd_prices(mints: List[str]) -> Dict[str, Optional[float]]:
    """USD price per mint from Jupiter Price API v3.

    Requests are chunked (the whale wallets W2's full-mint scan surfaces
    can hold hundreds of tokens and blow the URL length limit — HTTP 414
    observed live 2026-09-27). A mint missing from every response maps to
    None (unavailable) rather than a made-up number.
    """
    if not mints:
        return {}
    out: Dict[str, Optional[float]] = {}
    chunk = 25
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(mints), chunk):
            batch = mints[i : i + chunk]
            out.update(await _get_usd_prices_batch(session, batch))
    return out


@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def _get_usd_prices_batch(
    session: aiohttp.ClientSession, mints: List[str]
) -> Dict[str, Optional[float]]:
    url = f"{PRICE_API_URL}?ids={','.join(mints)}"
    async with session.get(url) as resp:
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
    """Native SOL + EVERY SPL token balance (Token & Token-2022) for one
    wallet, via two program-scoped RPC calls (W2: no per-mint allowlist).

    Each row: {mint, amount, decimals}. Tokens the wallet does not hold are
    simply absent — never zero-filled with guesses. ``symbol`` is filled by
    the registry in :func:`build_portfolio_balances`, not here.
    """
    balances: List[Dict] = []
    async with aiohttp.ClientSession() as session:
        result = await _rpc_call(
            session, rpc_url, "getBalance", [wallet, {"commitment": "confirmed"}]
        )
        balances.append(
            {
                "mint": "So11111111111111111111111111111111111111112",
                "amount": result["value"] / (10**9),
                "decimals": 9,
            }
        )

        by_mint: Dict[str, float] = {}
        dec_by_mint: Dict[str, int] = {}
        for program in TOKEN_PROGRAMS:
            result = await _rpc_call(
                session,
                rpc_url,
                "getTokenAccountsByOwner",
                [
                    wallet,
                    {"programId": program},
                    {"encoding": "jsonParsed", "commitment": "confirmed"},
                ],
            )
            for acc in result.get("value", []):
                info = acc["account"]["data"]["parsed"]["info"]
                mint = info["mint"]
                amt = info["tokenAmount"]
                by_mint[mint] = by_mint.get(mint, 0.0) + float(amt.get("uiAmount") or 0.0)
                dec_by_mint[mint] = int(amt.get("decimals", 0))
        for mint, total in by_mint.items():
            if total > 0:
                balances.append(
                    {"mint": mint, "amount": total, "decimals": dec_by_mint[mint]}
                )
    return balances


async def build_portfolio_balances(
    wallet: str, rpc_url: str, conn=None
) -> List[Dict]:
    """Balances enriched with registry symbols and real USD prices.

    Rows without a price carry usd_price=None / usd_value=None; rows whose
    metadata cannot be resolved carry symbol=None. Neither is ever guessed.
    When ``conn`` (SQLite) is given, the token registry caches metadata for
    every mint seen.
    """
    balances = await get_wallet_balances(wallet, rpc_url)
    mints = [b["mint"] for b in balances]
    prices = await get_usd_prices(mints) if mints else {}

    symbols: Dict[str, Optional[str]] = {}
    if conn is not None and mints:
        from .token_registry import resolve_mints

        hints = {b["mint"]: b["decimals"] for b in balances}
        infos = await resolve_mints(conn, mints, rpc_url, decimals_hint=hints)
        symbols = {m: (infos.get(m) or {}).get("symbol") for m in mints}

    for b in balances:
        b["symbol"] = symbols.get(b["mint"])
        price = prices.get(b["mint"])
        b["usd_price"] = price
        b["usd_value"] = None if price is None else b["amount"] * price
    return balances
