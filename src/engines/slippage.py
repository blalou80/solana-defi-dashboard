"""Real-time execution and slippage engine using Jupiter API."""

import logging
from typing import Dict, List, Optional, Tuple

import aiohttp
import pandas as pd

from ..models import Trade
from ..utils import async_retry

logger = logging.getLogger(__name__)

# Token decimals for known tokens
TOKEN_DECIMALS = {
    "So11111111111111111111111111111111111111112": 9,  # SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": 6,  # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": 6,  # USDT
    # Add more as needed
}

# Jupiter Swap API v1 (the v6 quote-api endpoint was retired in 2024).
JUPITER_QUOTE_URL = "https://lite-api.jup.ag/swap/v1/quote"

def natural_to_smallest(amount: float, mint: str) -> int:
    """Convert natural units (e.g., SOL) to smallest units (lamports)."""
    decimals = TOKEN_DECIMALS.get(mint, 9)  # default 9
    return int(amount * (10 ** decimals))

@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_quote(token_in: str, token_out: str, amount: float) -> Dict:
    """
    Fetch quote from Jupiter Swap API v1.
    Returns raw JSON response.
    """
    amount_smallest = natural_to_smallest(amount, token_in)
    url = JUPITER_QUOTE_URL
    params = {
        "inputMint": token_in,
        "outputMint": token_out,
        "amount": str(amount_smallest),
        "slippageBps": "50",
    }
    async with aiohttp.ClientSession() as session, session.get(url, params=params) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"Jupiter API error {resp.status}: {text}")
        data = await resp.json()
        return data

def compute_slippage_metrics(quote_data: Dict) -> pd.DataFrame:
    """
    Process a Jupiter swap/v1 quote and return a DataFrame with route metrics.
    One row per swap step in the route plan.
    Columns: route, expected_price, price_impact_pct, slippage_est, fill_probability.

    expected_price is None when token decimals are unknown — we never guess.
    """
    columns = ['route', 'expected_price', 'price_impact_pct', 'slippage_est', 'fill_probability']
    plan = quote_data.get('routePlan') or []
    if not plan:
        return pd.DataFrame(columns=columns)

    in_mint = quote_data.get('inputMint', '')
    out_mint = quote_data.get('outputMint', '')
    price_impact_pct = float(quote_data.get('priceImpactPct', 0)) * 100  # fraction -> pct
    slippage_est = float(quote_data.get('slippageBps', 0)) / 100  # bps -> pct

    expected_price = None
    try:
        if in_mint in TOKEN_DECIMALS and out_mint in TOKEN_DECIMALS:
            in_nat = int(quote_data['inAmount']) / (10 ** TOKEN_DECIMALS[in_mint])
            out_nat = int(quote_data['outAmount']) / (10 ** TOKEN_DECIMALS[out_mint])
            if in_nat > 0:
                expected_price = out_nat / in_nat
    except (KeyError, ValueError):
        expected_price = None

    rows = []
    for step in plan:
        swap = step.get('swapInfo', {})
        rows.append({
            'route': swap.get('label') or swap.get('ammKey', 'unknown'),
            'expected_price': expected_price if expected_price is not None else 'unavailable',
            'price_impact_pct': price_impact_pct,
            'slippage_est': slippage_est,
            'fill_probability': None,  # not provided by the API; never fabricated
            'percent': float(step.get('percent', 0)),
        })

    return pd.DataFrame(rows, columns=columns + ['percent'])

async def compare_routes(token_in: str, token_out: str, amount: float) -> pd.DataFrame:
    """High-level function to get quote and return route comparison DataFrame."""
    quote = await get_quote(token_in, token_out, amount)
    df = compute_slippage_metrics(quote)
    return df

@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_transaction_receipt(tx_hash: str, rpc_url: str) -> Dict:
    """Fetch a parsed transaction receipt via JSON-RPC."""
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "getTransaction",
        "params": [tx_hash, {"encoding": "jsonParsed",
                             "maxSupportedTransactionVersion": 0}],
    }
    async with aiohttp.ClientSession() as session, session.post(rpc_url, json=payload) as resp:
        data = await resp.json()
    if "error" in data or data.get("result") is None:
        raise Exception(f"receipt fetch failed for {tx_hash}: {str(data.get('error'))[:120]}")
    return data["result"]


def token_deltas_from_receipt(tx_json: Dict, owner: str) -> List[Tuple[str, float]]:
    """Per-(mint) uiTokenAmount deltas for one owner in a parsed receipt.

    Returns [(mint, delta)] sorted by absolute delta; positive = received,
    negative = sent. Pure parsing of real chain data — no assumptions about
    which side is the swap.
    """
    meta = tx_json.get("meta") or {}
    pre = {}
    for b in meta.get("preTokenBalances") or []:
        if b.get("owner") == owner:
            pre[(b["mint"], b["accountIndex"])] = float(
                b["uiTokenAmount"].get("uiAmount") or 0.0
            )
    post = {}
    for b in meta.get("postTokenBalances") or []:
        if b.get("owner") == owner:
            post[(b["mint"], b["accountIndex"])] = float(
                b["uiTokenAmount"].get("uiAmount") or 0.0
            )
    by_mint: Dict[str, float] = {}
    for key in set(pre) | set(post):
        mint = key[0]
        delta = post.get(key, 0.0) - pre.get(key, 0.0)
        by_mint[mint] = by_mint.get(mint, 0.0) + delta
    return sorted(by_mint.items(), key=lambda kv: abs(kv[1]), reverse=True)


async def realized_slippage_from_tx(
    tx_hash: str, owner: str, expected_out: float, out_mint: str, rpc_url: str
) -> Optional[float]:
    """Realized slippage % measured from the on-chain receipt.

    realized = received amount of ``out_mint`` by ``owner`` in that tx.
    Positive = worse than expected. Returns None when the receipt does not
    contain a movement of ``out_mint`` — never substitutes a guess.
    """
    tx = await get_transaction_receipt(tx_hash, rpc_url)
    deltas = token_deltas_from_receipt(tx, owner)
    for mint, delta in deltas:
        if mint == out_mint:
            received = delta
            if expected_out == 0:
                return None
            return (expected_out - received) / expected_out * 100
    logger.warning(
        f"Receipt {tx_hash} has no {out_mint[:8]}… movement for {owner[:8]}… "
        "— realized slippage unavailable."
    )
    return None


def realized_slippage(trade: Trade, rpc_url: str) -> Optional[float]:
    """
    Given a Trade object, fetch on-chain receipt and compute realized slippage.
    Returns realized slippage percentage (positive means worse than expected).
    """
    if not trade.amount_out_realized:
        logger.warning("Trade has no realized amount; cannot compute slippage.")
        return None
    expected = trade.amount_out_expected
    realized = trade.amount_out_realized
    if expected == 0:
        return None
    slippage = (expected - realized) / expected * 100
    return slippage

def parse_quote_for_trade(quote_data: Dict) -> Tuple[float, float, float]:
    """
    Extract price impact (pct), estimated slippage (pct), and expected output
    (smallest units) from a Jupiter swap/v1 quote.
    """
    if not quote_data.get('routePlan'):
        return 0.0, 0.0, 0.0
    price_impact = float(quote_data.get('priceImpactPct', 0)) * 100
    slippage_pct = float(quote_data.get('slippageBps', 0)) / 100
    out_amount = float(quote_data.get('outAmount', 0))
    return price_impact, slippage_pct, out_amount
