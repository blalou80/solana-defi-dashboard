"""CL Position Monitor dashboard component for displaying CL position data."""

import logging
from typing import List, Optional

import pandas as pd
import streamlit as st

from src.models import CLPosition
from src.services.cl_position_service import CLPositionMonitorService
from src.services.fee_harvester import FeeHarvesterService

logger = logging.getLogger(__name__)


def render_cl_position_monitor(
    positions: Optional[List[CLPosition]] = None,
    monitor_service: Optional[CLPositionMonitorService] = None,
    fee_harvester_service: Optional[FeeHarvesterService] = None,
) -> None:
    """Render the CL Position Monitor dashboard component.

    Args:
        positions: List of CLPosition objects (if any).
        monitor_service: The CLPositionMonitorService instance (if any).
        fee_harvester_service: The FeeHarvesterService instance (if any).
    """
    st.subheader("💧 CL Position Monitor")

    # Controls
    with st.container():
        st.markdown("### Manage Positions")
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            position_id = st.text_input("Position ID", key="cl_position_id")
        with col2:
            dex = st.selectbox(
                "DEX",
                options=["Orca", "Raydium"],
                index=0,
                key="cl_dex",
            )
        with col3:
            if st.button("Add Position", key="add_cl_position_btn"):
                # Validation
                if not position_id:
                    st.error("Position ID is required.")
                    logger.error("Attempted to add position with empty ID")
                    return
                if not dex:
                    st.error("DEX must be selected.")
                    logger.error("Attempted to add position without selecting DEX")
                    return

                # In a real implementation, we would add the position to the monitor service
                st.info(f"Position {position_id} added for {dex} (placeholder)")
                logger.info(f"Added position {position_id} for {dex}")

    # Display positions
    if positions is None:
        positions = []

    if not positions:
        st.info("No positions to display. Add a position to get started.")
    else:
        st.markdown("### 📊 Position Overview")

        # Prepare data for display
        position_data = []
        for pos in positions:
            position_data.append({
                "Position ID": pos.position_id[:8] + "...",
                "DEX": pos.dex_name,
                "Token A": pos.token_a,
                "Token B": pos.token_b,
                "Current Tick": pos.current_tick,
                "Tick Range": f"[{pos.tick_lower}, {pos.tick_upper}]",
                "In Range": "✅" if pos.is_in_range else "❌",
                "Liquidity": f"{pos.liquidity:,.2f}",
                "Fees A": f"{pos.fees_owed_a:,.4f}",
                "Fees B": f"{pos.fees_owed_b:,.4f}",
                "IL (%)": f"{pos.impermanent_loss:.2f}%",
                "Net Yield (%)": f"{pos.net_yield_estimate:.2f}%",
                "Last Updated": pos.last_updated.strftime("%H:%M:%S")
            })

        if position_data:
            df = pd.DataFrame(position_data)
            st.dataframe(df, hide_index=True, use_container_width=True)

        # Detailed view for selected position
        st.markdown("### 🔍 Position Details")
        selected_pos_id = st.selectbox(
            "Select Position for Details",
            options=[p.position_id for p in positions],
            format_func=lambda x: x[:8] + "...",
            key="selected_cl_position"
        )

        if selected_pos_id:
            selected_pos = next((p for p in positions if p.position_id == selected_pos_id), None)
            if selected_pos:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Impermanent Loss", f"{selected_pos.impermanent_loss:.2f}%")
                    st.metric("Fees Earned (A)", f"{selected_pos.fees_owed_a:,.4f}")
                    st.metric("Fees Earned (B)", f"{selected_pos.fees_owed_b:,.4f}")
                with col2:
                    st.metric("Net Yield Estimate", f"{selected_pos.net_yield_estimate:.2f}%")
                    st.metric("Liquidity", f"{selected_pos.liquidity:,.2f}")
                    st.metric("Price Range", f"[{selected_pos.tick_lower}, {selected_pos.tick_upper}]")

                # Action buttons
                st.markdown("### ⚡ Actions")
                action_col1, action_col2, action_col3 = st.columns(3)
                with action_col1:
                    if st.button("💰 Harvest Fees", key="harvest_fees_btn"):
                        # Validation
                        if not selected_pos:
                            st.error("No position selected.")
                            logger.error("Attempted to harvest fees without selecting a position")
                            return
                        # In a real implementation, we would call the fee harvester service
                        st.info(f"Fee harvesting initiated for position {selected_pos.position_id} (placeholder)")
                        logger.info(f"Fee harvesting initiated for position {selected_pos.position_id}")
                with action_col2:
                    if st.button("🔄 Refresh Data", key="refresh_cl_data_btn"):
                        # Validation
                        if not selected_pos:
                            st.error("No position selected.")
                            logger.error("Attempted to refresh data without selecting a position")
                            return
                        # In a real implementation, we would call the monitor service to update the position
                        st.info(f"Refreshing data for position {selected_pos.position_id} (placeholder)")
                        logger.info(f"Refreshing data for position {selected_pos.position_id}")
                with action_col3:
                    if st.button("📈 View IL Projection", key="view_il_projection_btn"):
                        # Validation
                        if not selected_pos:
                            st.error("No position selected.")
                            logger.error("Attempted to view IL projection without selecting a position")
                            return
                        st.info(f"IL projection for position {selected_pos.position_id} (placeholder)")
                        logger.info(f"Viewing IL projection for position {selected_pos.position_id}")

# Example usage for testing
if __name__ == "__main__":
    st.set_page_config(page_title="CL Position Monitor", layout="wide")
    render_cl_position_monitor()
