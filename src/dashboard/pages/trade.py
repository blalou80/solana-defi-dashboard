import asyncio

import pandas as pd
import streamlit as st

from src.engines.slippage import compare_routes
from src.state import get_state

st.set_page_config(page_title="Trade Slippage Analysis", layout="wide")

st.title("Real-Time Slippage Analysis")

st.markdown("""
Get a quote from Jupiter and compare routes for a given token pair.
""")

# Inputs
col1, col2, col3 = st.columns(3)
with col1:
    token_in = st.text_input("Token In (mint address)", "So11111111111111111111111111111111111111112")
with col2:
    token_out = st.text_input("Token Out (mint address)", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
with col3:
    amount = st.number_input("Amount (in natural units)", min_value=0.0, value=1.0, step=0.1)

if st.button("Get Quote"):
    with st.spinner("Fetching quote..."):
        try:
            # Run async function
            df = asyncio.run(compare_routes(token_in, token_out, amount))
            if df.empty:
                st.warning("No routes found.")
            else:
                st.success("Quote fetched successfully!")
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Error fetching quote: {e}")

st.markdown("---")
st.subheader("Recent Trades")
# Placeholder for trade history
state = get_state()
trades = state.trades[-5:] if state.trades else []
if trades:
    # Convert to DataFrame for display
    trade_data = [{
        "Time": t.timestamp.strftime("%H:%M:%S"),
        "Token In": t.token_in[:8] + "...",
        "Token Out": t.token_out[:8] + "...",
        "Amount In": t.amount_in,
        "Expected Out": t.amount_out_expected,
        "Realized Out": t.amount_out_realized,
        "Slippage %": round(t.slippage_realized, 2) if t.slippage_realized is not None else "N/A"
    } for t in trades]
    st.dataframe(pd.DataFrame(trade_data), use_container_width=True)
else:
    st.info("No trades recorded yet.")
