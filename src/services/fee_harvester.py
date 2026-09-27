"""Fee Harvesting service for collecting fees from concentrated liquidity positions."""

import logging
from typing import Any, Dict

from ..models.cl_position import CLPosition
from ..services.solana_rpc_client import SolanaRpcClient
from ..utils.error_handling import SimulationError

logger = logging.getLogger(__name__)


class FeeHarvesterService:
    """Service for harvesting fees from concentrated liquidity positions."""

    def __init__(self, rpc_endpoint: str):
        self.rpc_client = SolanaRpcClient(rpc_endpoint)

    async def close(self):
        """Close the RPC client."""
        await self.rpc_client.close()

    async def harvest_fees(
        self,
        position: CLPosition,
    ) -> Dict[str, Any]:
        """Harvest fees from a concentrated liquidity position.

        Args:
            position: The CLPosition to harvest fees from.

        Returns:
            A dictionary containing the harvest results.

        Raises:
            SimulationError: always, until real transaction building against
            the DEX position program exists (Phase 1+). The previous version
            "harvested" fees by multiplying local fields by 0.8 and inventing
            a gas figure — a fabricated result, removed in the 2026-09
            honesty pass.
        """
        raise SimulationError(
            f"Fee harvesting for position {position.position_id} is not "
            "implemented: it requires building and sending a real on-chain "
            "collect transaction. Refusing to return mock harvest results."
        )


# Example usage
if __name__ == "__main__":
    # This is just for demonstration.
    harvester = FeeHarvesterService("http://localhost:8899")
    print("FeeHarvesterService initialized.")
