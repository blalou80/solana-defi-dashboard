"""CL Position Monitor service for monitoring concentrated liquidity positions."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.cl_position import CLPosition
from ..services.solana_rpc_client import SolanaRpcClient

logger = logging.getLogger(__name__)


class CLPositionMonitorService:
    """Service for monitoring concentrated liquidity positions."""

    def __init__(self, rpc_endpoint: str):
        self.rpc_client = SolanaRpcClient(rpc_endpoint)
        self.positions: Dict[str, CLPosition] = {}  # position_id -> CLPosition
        self.alerts_sent: Dict[str, datetime] = {}  # position_id -> last_alert_time

    async def close(self):
        """Close the RPC client."""
        await self.rpc_client.close()

    async def add_position(self, position: CLPosition) -> None:
        """Add a position to monitor.

        Args:
            position: The CLPosition to monitor.
        """
        self.positions[position.position_id] = position
        logger.info(f"Added position {position.position_id} to monitoring")

    async def remove_position(self, position_id: str) -> bool:
        """Remove a position from monitoring.

        Args:
            position_id: The ID of the position to remove.

        Returns:
            True if position was removed, False if not found.
        """
        if position_id in self.positions:
            del self.positions[position_id]
            # Also clear any alert history
            if position_id in self.alerts_sent:
                del self.alerts_sent[position_id]
            logger.info(f"Removed position {position_id} from monitoring")
            return True
        return False

    async def update_position_data(self, position_id: str) -> Optional[CLPosition]:
        """Update position data from blockchain.

        Args:
            position_id: The ID of the position to update.

        Returns:
            Updated CLPosition if found, None otherwise.

        NOTE: on-chain tick/fee fetching is not implemented yet (Phase 1).
        The previous version random-walked the stored tick and invented fee
        accrual — fabricated data presented as monitoring. It now returns
        the stored position untouched and logs the missing integration.
        """
        if position_id not in self.positions:
            logger.warning(f"Position {position_id} not found for update")
            return None

        logger.warning(
            f"update_position_data({position_id}): no on-chain ingestion "
            "connected (Phase 1) — returning stored values unchanged; "
            "no data was simulated."
        )
        return self.positions[position_id]

    async def check_and_trigger_alerts(self, position_id: str, alert_threshold_minutes: int = 5) -> List[Dict[str, Any]]:
        """Check if position needs alerts and trigger them if needed.

        Args:
            position_id: The ID of the position to check.
            alert_threshold_minutes: Minimum minutes between alerts for same position.

        Returns:
            List of alerts triggered.
        """
        if position_id not in self.positions:
            return []

        position = self.positions[position_id]
        alerts = []

        # Check for out of range
        if not position.is_in_range:
            last_alert = self.alerts_sent.get(position_id)
            now = datetime.now()

            # Check if enough time has passed since last alert
            if last_alert is None or (now - last_alert).total_seconds() > (alert_threshold_minutes * 60):
                alert = {
                    "type": "out_of_range",
                    "position_id": position_id,
                    "message": f"Position {position_id} is out of range. Current tick: {position.current_tick}, Range: [{position.tick_lower}, {position.tick_upper}]",
                    "timestamp": now,
                    "severity": "high"
                }
                alerts.append(alert)
                self.alerts_sent[position_id] = now
                logger.warning(f"Triggered out of range alert for position {position_id}")

        # Check for extreme impermanent loss
        if position.impermanent_loss > 50.0:  # More than 50% IL
            last_alert = self.alerts_sent.get(f"{position_id}_il")
            now = datetime.now()

            if last_alert is None or (now - last_alert).total_seconds() > (alert_threshold_minutes * 60):
                alert = {
                    "type": "high_impermanent_loss",
                    "position_id": position_id,
                    "message": f"Position {position_id} has high impermanent loss: {position.impermanent_loss:.2f}%",
                    "timestamp": now,
                    "severity": "medium"
                }
                alerts.append(alert)
                self.alerts_sent[f"{position_id}_il"] = now
                logger.warning(f"Triggered high IL alert for position {position_id}")

        return alerts

    async def get_position_status(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a position.

        Args:
            position_id: The ID of the position.

        Returns:
            Position status dictionary if found, None otherwise.
        """
        if position_id not in self.positions:
            return None

        position = self.positions[position_id]
        return {
            "position_id": position.position_id,
            "dex_name": position.dex_name,
            "pool_address": position.pool_address,
            "token_a": position.token_a,
            "token_b": position.token_b,
            "tick_lower": position.tick_lower,
            "tick_upper": position.tick_upper,
            "current_tick": position.current_tick,
            "liquidity": position.liquidity,
            "fees_owed_a": position.fees_owed_a,
            "fees_owed_b": position.fees_owed_b,
            "impermanent_loss": position.impermanent_loss,
            "is_in_range": position.is_in_range,
            "last_updated": position.last_updated.isoformat(),
            "net_yield_estimate": position.net_yield_estimate
        }

    async def get_all_positions_status(self) -> List[Dict[str, Any]]:
        """Get status of all monitored positions.

        Returns:
            List of position status dictionaries.
        """
        statuses = []
        for position_id in self.positions:
            status = await self.get_position_status(position_id)
            if status:
                statuses.append(status)
        return statuses


# Example usage
if __name__ == "__main__":
    # This is just for demonstration.
    monitor = CLPositionMonitorService("http://localhost:8899")
    print("CLPositionMonitorService initialized.")
