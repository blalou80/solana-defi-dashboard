import streamlit as st
import pandas as pd
from src.config import load_config
from src.state import get_state
from src.utils import setup_logging

# Setup logging
setup_logging()

st.set_page_config(page_title="Solana DeFi Analytics", layout="wide")

st.title("Solana DeFi Analytics & Risk Management Dashboard")

# Sidebar for config info
st.sidebar.header("Configuration")
try:
    config = load_config()
    st.sidebar.write(f"RPC: {config.rpc_endpoint[:30]}...")
    st.sidebar.write(f"Polling interval: {config.polling_interval_sec}s")
    st.sidebar.write(f"Risk window: {config.risk_window_days} days")
except Exception as e:
    st.sidebar.error(f"Error loading config: {e}")

# Main area
st.header("Portfolio Summary")
state = get_state()
if state.portfolio:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Value (USD)", f"${state.portfolio.total_value_usd:,.2f}")
    with col2:
        st.metric("VaR (95%)", f"${state.portfolio.var_95:,.2f}")
    with col3:
        st.metric("Sharpe Ratio", f"{state.portfolio.sharpe_ratio:.2f}")
    st.subheader("Token Exposure")
    if state.portfolio.token_exposures:
        st.dataframe(pd.DataFrame(list(state.portfolio.token_exposures.items()), columns=["Token", "Value (USD)"]))
else:
    st.info("No portfolio data available. Start monitoring positions.")

# Navigation (using pages)
st.markdown("---")
st.markdown("Use the sidebar to navigate to Trade, Positions, and Alerts pages.")