"""Real-time execution and slippage engine using Jupiter API."""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import pandas as pd
import aiohttp
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey as PublicKey

from ..utils import async_retry
from ..models import Trade
from ..state import get_state, add_trade

logger = logging.getLogger(__name__)

# Token decimals for known tokens (hardcoded for MVP)
TOKEN_DECIMALS = {
    "So11111111111111111111111111111111111111112": 9,  # SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": 6,  # USDC
    # Add more as needed
}

def natural_to_smallest(amount: float, mint: str) -> int:
    """Convert natural units (e.g., SOL) to smallest units (lamports)."""
    decimals = TOKEN_DECIMALS.get(mint, 9)  # default 9
    return int(amount * (10 ** decimals))

@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_quote(token_in: str, token_out: str, amount: float) -> Dict:
    """
    Fetch quote from Jupiter API.
    Returns raw JSON response.
    """
    amount_smallest = natural_to_smallest(amount, token_in)
    url = f"https://quote-api.jup.ag/v6/quote?inputMint={token_in}&outputMint={token_out}&amount={amount_smallest}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Jupiter API error {resp.status}: {text}")
            data = await resp.json()
            return data

def compute_slippage_metrics(quote_data: Dict) -> pd.DataFrame:
    """
    Process quote data and return DataFrame with route metrics.
    Columns: route, expected_price, price_impact_pct, slippage_est, fill_probability.
    """
    routes = quote_data.get('routes', [])
    if not routes:
        return pd.DataFrame(columns=['route', 'expected_price', 'price_impact_pct', 'slippage_est', 'fill_probability'])

    rows = []
    for route in routes:
        market_infos = route.get('marketInfos', [])
        if not market_infos:
            continue
        mi = market_infos[0]
        route_name = mi.get('amm', 'unknown')
        price_impact_pct = float(route.get('priceImpactPct', 0))
        slippage_est = float(route.get('slippageBps', 0)) / 100  # basis points to percentage
        fill_prob = float(route.get('fillProbability', 0))
        row = {
            'route': route_name,
            'expected_price': 'N/A',  # TODO: compute actual price
            'price_impact_pct': price_impact_pct,
            'slippage_est': slippage_est,
            'fill_probability': fill_prob
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    return df

async def compare_routes(token_in: str, token_out: str, amount: float) -> pd.DataFrame:
    """High-level function to get quote and return route comparison DataFrame."""
    quote = await get_quote(token_in, token_out, amount)
    df = compute_slippage_metrics(quote)
    return df

@async_retry(max_attempts=3, delay=1.0, backoff=2.0)
async def get_transaction_receipt(tx_hash: str, rpc_url: str) -> Dict:
    """Fetch transaction receipt from Solana RPC."""
    client = AsyncClient(rpc_url)
    try:
        resp = await client.get_transaction(tx_hash, encoding='json', commitment='confirmed')
        return resp
    finally:
        await client.close()

async def realized_slippage(trade: Trade, rpc_url: str) -> Optional[float]:
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

def add_trade_record(trade: Trade) -> None:
    """Store trade in state."""
    add_trade(trade)
    logger.info(f"Trade recorded: {trade.id}")

def parse_quote_for_trade(quote_data: Dict, route_index: int = 0) -> Tuple[float, float, float]:
    """
    Extract price impact, estimated slippage, and expected output from a specific route.
    Returns (price_impact_pct, slippage_est, out_amount).
    """
    routes = quote_data.get('routes', [])
    if not routes or route_index >= len(routes):
        return 0.0, 0.0, 0.0
    route = routes[route_index]
    price_impact = float(route.get('priceImpactPct', 0))
    slippage_bps = float(route.get('slippageBps', 0))
    slippage_pct = slippage_bps / 100
    out_amount = float(route.get('outAmount', 0))
    return price_impact, slippage_pct, out_amount