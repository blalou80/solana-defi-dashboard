"""Trade Analyzer dashboard component for displaying DEX quotes and trade analysis."""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from src.models import RouteComparison, TradeRequest

logger = logging.getLogger(__name__)


def render_trade_analyzer(
    trade_request: Optional[TradeRequest] = None,
    route_comparisons: Optional[List[RouteComparison]] = None,
    analysis: Optional[Dict[str, Any]] = None,
) -> None:
    """Render the Trade Analyzer dashboard component.

    Args:
        trade_request: The parsed trade request (if any).
        route_comparisons: List of route comparisons from DEXs (if any).
        analysis: Analysis results from SlippageAnalyticsService (if any).
    """
    st.subheader("🔍 Trade Analyzer")

    # Input section
    with st.container():
        st.markdown("### Enter Trade Request")
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            amount = st.number_input(
                "Amount", min_value=0.0, value=5.0, step=0.1, key="trade_amount"
            )
        with col2:
            token_in = st.selectbox(
                "Input Token",
                options=["SOL", "USDC", "USDT", "BONK"],
                index=0,
                key="trade_token_in",
            )
        with col3:
            token_out = st.selectbox(
                "Output Token",
                options=["USDC", "SOL", "USDT", "BONK"],
                index=0 if token_in != "USDC" else 1,
                key="trade_token_out",
            )
        intent = st.selectbox(
            "Execution Preference",
            options=["low_slippage", "fast_execution", "best_output"],
            format_func=lambda x: {
                "low_slippage": "Low Slippage",
                "fast_execution": "Fast Execution",
                "best_output": "Best Output",
            }[x],
            key="trade_intent",
        )

        if st.button("Analyze Trade", type="primary", key="analyze_trade_btn"):
            # Validate inputs
            if amount <= 0:
                st.error("Amount must be greater than zero.")
                logger.error(f"Invalid trade request: amount must be > 0, got {amount}")
                return
            if token_in == token_out:
                st.error("Input and output tokens must be different.")
                logger.error(f"Invalid trade request: input and output tokens are the same: {token_in}")
                return

            # Log the trade request
            logger.info(f"Trade request received: {amount} {token_in} for {token_out} with intent {intent}")

            # In a real implementation, we would:
            # 1. Parse the natural language (if needed) or use the inputs directly
            # 2. Call the DEX Aggregator service to get quotes
            # 3. Analyze the results
            # 4. Update the state and rerun
            st.info("Trade analysis would be performed here (placeholder)")
            # For now, we'll show some mock data
            st.session_state.show_mock_results = True

    # Show mock results if button was clicked
    if st.session_state.get("show_mock_results", False):
        st.markdown("### 📊 Route Comparison")

        # Mock data for demonstration
        mock_routes = [
            {
                "DEX": "Jupiter",
                "Expected Price": 98.50,
                "Price Impact (%)": 0.12,
                "Slippage Estimate (%)": 0.15,
                "Fill Probability": 0.98,
                "Volatility Estimate": 0.008,
                "Gas Estimate (SOL)": 0.0005,
                "Best Route": True,
            },
            {
                "DEX": "Raydium",
                "Expected Price": 98.45,
                "Price Impact (%)": 0.18,
                "Slippage Estimate (%)": 0.22,
                "Fill Probability": 0.95,
                "Volatility Estimate": 0.012,
                "Gas Estimate (SOL)": 0.0003,
                "Best Route": False,
            },
            {
                "DEX": "Orca",
                "Expected Price": 98.40,
                "Price Impact (%)": 0.25,
                "Slippage Estimate (%)": 0.30,
                "Fill Probability": 0.92,
                "Volatility Estimate": 0.015,
                "Gas Estimate (SOL)": 0.0004,
                "Best Route": False,
            },
        ]

        df = pd.DataFrame(mock_routes)
        # Format the dataframe for better display
        display_df = df.copy()
        display_df["Expected Price"] = display_df["Expected Price"].apply(lambda x: f"${x:.2f}")
        display_df["Price Impact (%)"] = display_df["Price Impact (%)"].apply(lambda x: f"{x:.2f}%")
        display_df["Slippage Estimate (%)"] = display_df["Slippage Estimate (%)"].apply(lambda x: f"{x:.2f}%")
        display_df["Fill Probability"] = display_df["Fill Probability"].apply(lambda x: f"{x:.0%}")
        display_df["Volatility Estimate"] = display_df["Volatility Estimate"].apply(lambda x: f"{x:.3f}")
        display_df["Gas Estimate (SOL)"] = display_df["Gas Estimate (SOL)"].apply(lambda x: f"{x:.6f}")
        display_df["Best Route"] = display_df["Best Route"].apply(lambda x: "⭐" if x else "")

        st.dataframe(display_df, hide_index=True, use_container_width=True)

        # Analysis section
        st.markdown("### 📈 Analysis")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Best Route", "Jupiter", "⭐ Lowest Slippage")
        with col2:
            st.metric("Price Impact Range", "0.12% - 0.25%", "0.13% spread")
        with col3:
            st.metric("Avg. Fill Probability", "95%", "High confidence")

        # Action buttons
        st.markdown("### ⚡ Actions")
        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            if st.button("📝 Save as Template", key="save_template_btn"):
                st.success("Trade configuration saved as template!")
        with action_col2:
            if st.button("🧪 Simulate Trade", key="simulate_trade_btn"):
                st.info("Transaction simulation would be executed here (placeholder)")
        with action_col3:
            if st.button("🔄 Refresh Quotes", key="refresh_quotes_btn"):
                st.info("Quotes would be refreshed here (placeholder)")


# Example usage for testing
if __name__ == "__main__":
    st.set_page_config(page_title="Trade Analyzer", layout="wide")
    render_trade_analyzer()
