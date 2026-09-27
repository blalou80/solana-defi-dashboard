"""DEX API clients for Jupiter, Raydium, and Orca with rate limiting."""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import aiohttp

from .utils import async_retry

logger = logging.getLogger(__name__)


class DexApiClient:
    """Base class for DEX API clients."""

    def __init__(self, base_url: str, rate_limit_per_sec: float = 5.0):
        self.base_url = base_url
        self.rate_limit_per_sec = rate_limit_per_sec
        self.min_interval = 1.0 / rate_limit_per_sec if rate_limit_per_sec > 0 else 0
        self.last_request_time = 0.0
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _rate_limit(self):
        """Enforce rate limiting by ensuring minimum interval between requests."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request with retry and rate limiting."""
        await self._rate_limit()
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        try:
            async with session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Request to {url} failed: {e}")
            raise


class JupiterApiClient(DexApiClient):
    """Client for Jupiter Swap API v1 (the v6 quote-api was retired in 2024)."""

    def __init__(self, rate_limit_per_sec: float = 5.0):
        super().__init__("https://lite-api.jup.ag/swap/v1", rate_limit_per_sec)

    @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
    ) -> Dict[str, Any]:
        """Get a quote from Jupiter."""
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": str(slippage_bps),
        }
        return await self._request("GET", "/quote", params=params)


class RaydiumApiClient(DexApiClient):
    """Client for Raydium's public info API.

    NOTE: Raydium exposes no public quote REST endpoint, so this client only
    provides pool metadata. It deliberately has no ``get_quote`` — fabricating
    one was removed in the 2026-09 honesty pass (see specs/product-audit).
    """

    def __init__(self, rate_limit_per_sec: float = 5.0):
        super().__init__("https://api.raydium.io/v2", rate_limit_per_sec)

    async def get_pool_info(self) -> Dict[str, Any]:
        """Get pool information from Raydium."""
        return await self._request("GET", "/sdk/liquidity/mainnet.json")


class OrcaApiClient(DexApiClient):
    """Client for Orca's public info API.

    NOTE: no public quote endpoint; metadata only. ``get_quote`` was removed
    because it never returned a quote (it fetched the token list).
    """

    def __init__(self, rate_limit_per_sec: float = 5.0):
        super().__init__("https://api.orca.so", rate_limit_per_sec)

    @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
    async def get_token_list(self) -> Dict[str, Any]:
        """Get Orca's token metadata list."""
        return await self._request("GET", "/token/list")


# Factory function to get a DEX client by name
def get_dex_client(dex_name: str, rate_limit_per_sec: float = 5.0) -> DexApiClient:
    """Factory function to get a DEX client by name."""
    clients = {
        "jupiter": JupiterApiClient,
        "raydium": RaydiumApiClient,
        "orca": OrcaApiClient,
    }
    client_class = clients.get(dex_name.lower())
    if not client_class:
        raise ValueError(f"Unsupported DEX: {dex_name}")
    return client_class(rate_limit_per_sec)
