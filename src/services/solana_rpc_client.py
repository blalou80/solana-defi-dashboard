"""Solana RPC client with retry logic and caching."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey
from solders.rpc.responses import GetHealthResp

from .utils import async_retry

logger = logging.getLogger(__name__)


class SolanaRpcClient:
    """Client for interacting with Solana RPC with retry and caching."""

    def __init__(self, endpoint: str, commitment: Optional[Commitment] = None):
        self.endpoint = endpoint
        self.client = AsyncClient(
            endpoint, commitment=commitment or Commitment("confirmed")
        )
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}

    async def close(self):
        """Close the RPC client."""
        await self.client.close()

    @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
    async def get_version(self) -> Dict[str, Any]:
        """Get the Solana node version."""
        response = await self.client.get_version()
        return response.to_json()

    @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
    async def get_health(self) -> str:
        """Get the health of the Solana node."""
        response: GetHealthResp = await self.client.get_health()
        return response.value

    @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
    async def get_account_info(self, pubkey: str) -> Optional[Dict[str, Any]]:
        """Get account info for a public key."""
        cache_key = f"account_info:{pubkey}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            response = await self.client.get_account_info(Pubkey.from_string(pubkey))
            if response.value is None:
                return None
            result = response.value.to_json()
            self._save_to_cache(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Failed to get account info for {pubkey}: {e}")
            raise

    @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
    async def get_signatures_for_address(
        self, address: str, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get signatures for an address."""
        cache_key = f"signatures:{address}:{limit}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            response = await self.client.get_signatures_for_address(
                Pubkey.from_string(address), limit=limit
            )
            # Convert each signature info to dict
            result = []
            for sig in response.value:
                result.append(sig.to_json())
            self._save_to_cache(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Failed to get signatures for {address}: {e}")
            raise

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Retrieve item from cache if not expired."""
        if key in self._cache:
            timestamp = self._cache_timestamps.get(key, 0)
            if asyncio.get_event_loop().time() - timestamp < 30:  # 30 seconds TTL
                return self._cache[key]
            else:
                # Remove expired cache
                del self._cache[key]
                del self._cache_timestamps[key]
        return None

    def _save_to_cache(self, key: str, value: Any) -> None:
        """Save item to cache with current timestamp."""
        self._cache[key] = value
        self._cache_timestamps[key] = asyncio.get_event_loop().time()
