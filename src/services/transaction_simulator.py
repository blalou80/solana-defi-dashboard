"""Transaction Simulator service for simulating trades on a local testnet fork."""

import logging
from typing import Any, Dict, Optional

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment

from ..models.route_comparison import RouteComparison
from ..models.trade_request import TradeRequest
from ..utils.error_handling import SimulationError

logger = logging.getLogger(__name__)


class TransactionSimulatorService:
    """Service for simulating transactions on a local testnet fork."""

    def __init__(self, rpc_endpoint: str):
        self.rpc_endpoint = rpc_endpoint
        self.client: Optional[AsyncClient] = None

    async def _get_client(self) -> AsyncClient:
        """Get or create the RPC client."""
        if self.client is None:
            self.client = AsyncClient(self.rpc_endpoint, commitment=Commitment("confirmed"))
        return self.client

    async def close(self):
        """Close the RPC client."""
        if self.client:
            await self.client.close()

    async def simulate_trade(
        self,
        route: RouteComparison,
        trade_request: TradeRequest,
    ) -> Dict[str, Any]:
        """Simulate a trade on the local testnet fork.

        Args:
            route: The selected route to simulate.
            trade_request: The original trade request.

        Returns:
            A dictionary containing the simulation results.

        Raises:
            SimulationError: always, until real transaction building +
            ``simulateTransaction`` against a fork is implemented (Phase 1+).
            The previous version returned fabricated "simulation" numbers
            derived from wall-clock jitter; faking a result was removed in
            the 2026-09 honesty pass.
        """
        raise SimulationError(
            "Transaction simulation is not implemented: building and "
            "simulating a real transaction requires the Phase 1 route "
            "builder. Refusing to return mock results."
        )


# Example usage
if __name__ == "__main__":
    # This is just for demonstration; in practice, the service is used by other components.
    # We would need to run this in an async context.
    async def main():
        simulator = TransactionSimulatorService("http://localhost:8899")  # example testnet fork
        # We would need a trade request and route to simulate
        # For now, just print that the service is initialized.
        print("TransactionSimulatorService initialized.")
        await simulator.close()

    # asyncio.run(main())
