"""DEX Aggregator service for fetching quotes from multiple DEXs."""

import asyncio
import logging
from typing import List, Optional

from ..models.route_comparison import RouteComparison
from ..models.trade_request import TradeRequest
from ..utils.error_handling import DataFetchError
from .dex_api_client import JupiterApiClient, OrcaApiClient, RaydiumApiClient
from .solana_rpc_client import SolanaRpcClient

logger = logging.getLogger(__name__)


class DexAggregatorService:
    """Service for aggregating quotes from multiple DEXs."""

    def __init__(
        self,
        rpc_endpoint: str,
        dex_rate_limit_per_sec: float = 5.0,
    ):
        self.rpc_client = SolanaRpcClient(rpc_endpoint)
        self.dex_clients = {
            "jupiter": JupiterApiClient(rate_limit_per_sec=dex_rate_limit_per_sec),
            "raydium": RaydiumApiClient(rate_limit_per_sec=dex_rate_limit_per_sec),
            "orca": OrcaApiClient(rate_limit_per_sec=dex_rate_limit_per_sec),
        }

    async def close(self):
        """Close all clients."""
        await self.rpc_client.close()
        for client in self.dex_clients.values():
            await client.close()

    async def get_quotes_for_trade(
        self,
        trade_request: TradeRequest,
    ) -> List[RouteComparison]:
        """Fetch quotes from all supported DEXs for a trade request.

        Only DEXs with a real quote source are queried. Raydium and Orca have
        no public quote API; they are reported as unavailable instead of
        being padded with fabricated numbers (2026-09 honesty pass).

        Args:
            trade_request: The parsed trade request.

        Returns:
            List of RouteComparison objects, one per DEX that succeeded.
        """
        # Prepare tasks for each DEX with a real quote source
        tasks = []
        dex_names = []

        for dex_name, client in self.dex_clients.items():
            if not hasattr(client, "get_quote"):
                logger.info(f"No live quote source for {dex_name}; skipping.")
                continue
            # Create a task for each DEX
            task = asyncio.create_task(
                self._fetch_quote_from_dex(
                    dex_name, client, trade_request
                )
            )
            tasks.append(task)
            dex_names.append(dex_name)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        route_comparisons = []
        for dex_name, result in zip(dex_names, results, strict=True):
            if isinstance(result, Exception):
                logger.warning(f"Failed to get quote from {dex_name}: {result}")
                continue
            if result is None:
                continue
            route_comparisons.append(result)

        # Sort by expected price (or slippage) to determine best route
        route_comparisons.sort(key=lambda x: x.slippage_estimate)
        if route_comparisons:
            route_comparisons[0].is_best_route = True

        return route_comparisons

    async def _fetch_quote_from_dex(
        self,
        dex_name: str,
        client,
        trade_request: TradeRequest,
    ) -> Optional[RouteComparison]:
        """Fetch a quote from a single DEX and convert to RouteComparison.

        Args:
            dex_name: Name of the DEX (jupiter, raydium, orca).
            client: The DEX API client instance.
            trade_request: The trade request for token info and amount.

        Returns:
            RouteComparison object or None if failed.
        """
        try:
            if dex_name == "jupiter":
                # For Jupiter, we need mint addresses
                token_map = {
                    "SOL": "So11111111111111111111111111111111111111112",
                    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
                }
                # Known token decimals, used for amount conversion and price math
                token_decimals = {
                    "SOL": 9,
                    "USDC": 6,
                    "USDT": 6,
                }
                input_mint = token_map.get(trade_request.token_in)
                output_mint = token_map.get(trade_request.token_out)
                if not input_mint or not output_mint:
                    logger.warning(f"Unknown token for Jupiter: {trade_request.token_in} or {trade_request.token_out}")
                    return None

                in_decimals = token_decimals.get(trade_request.token_in, 9)
                out_decimals = token_decimals.get(trade_request.token_out, 6)

                quote = await client.get_quote(
                    input_mint=input_mint,
                    output_mint=output_mint,
                    amount=int(trade_request.amount_in * (10 ** in_decimals)),
                    slippage_bps=50,  # 0.5% slippage tolerance
                )
                # Extract relevant fields from Jupiter's response
                in_amount = int(quote.get("inAmount", 0))
                out_amount = int(quote.get("outAmount", 0))
                if in_amount == 0 or out_amount == 0:
                    return None

                expected_price = (out_amount / (10 ** out_decimals)) / (
                    in_amount / (10 ** in_decimals)
                )
                price_impact_pct = float(quote.get("priceImpactPct", 0))
                slippage_bps = quote.get("slippageBps", 50)
                slippage_estimate = slippage_bps / 100.0  # convert bps to percent
                # fill_probability / volatility / gas are not provided by the
                # Jupiter quote API. Left at 0.0 = "not measured" — never
                # fabricated (see METRICS.md).
                route_path = f"{trade_request.token_in} → {trade_request.token_out}"

                return RouteComparison(
                    trade_request_id=trade_request.id,
                    dex_name=dex_name.capitalize(),
                    route_path=route_path,
                    expected_price=expected_price,
                    price_impact_pct=price_impact_pct,
                    slippage_estimate=slippage_estimate,
                    fill_probability=0.0,
                    volatility_estimate=0.0,
                    gas_estimate=0.0,
                    is_best_route=False,  # will be set later
                )

            else:
                logger.error(f"Unknown DEX: {dex_name}")
                return None

        except Exception as e:
            logger.error(f"Error fetching quote from {dex_name}: {e}")
            raise DataFetchError(f"Failed to fetch quote from {dex_name}: {e}") from e
