import pandas as pd
import streamlit as st

from src.config import load_config
from src.db import get_connection
from src.risk.metrics import compute_portfolio_metrics
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
    st.sidebar.write(f"Wallets watched: {len(config.wallet_addresses)}")
except Exception as e:
    st.sidebar.error(f"Error loading config: {e}")
    config = None

# Main area — data comes from the SQLite store written by the daemon
# (python -m src.main). Nothing on this page is ever mock data; missing
# data renders as an explicit unavailable state.
st.header("Portfolio Summary")

if config and config.wallet_addresses:
    conn = get_connection(config.db_path)
    for wallet in config.wallet_addresses:
        st.subheader(f"Wallet `{wallet[:8]}…{wallet[-4:]}`")
        p = compute_portfolio_metrics(conn, wallet)
        if p.snapshot_count == 0:
            st.info(
                "No stored snapshots for this wallet yet. Start the daemon "
                "(`python -m src.main`) — the dashboard reads what it persists."
            )
            continue
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Value (USD)", f"${p.total_value_usd:,.2f}")
        with col2:
            st.metric(
                "VaR (95%)",
                "unavailable" if p.var_95 is None else f"${p.var_95:,.2f}",
                help=(
                    f"Historical simulation over {p.snapshot_count} stored "
                    "snapshots; needs ≥ 20 samples."
                ),
            )
        with col3:
            st.metric(
                "Sharpe Ratio",
                "unavailable" if p.sharpe_ratio is None else f"{p.sharpe_ratio:.2f}",
                help=f"From snapshot returns; needs ≥ {5} samples.",
            )
        with col4:
            st.metric("Snapshots stored", p.snapshot_count)
        st.caption(
            f"Last update: {p.last_updated} · source: Solana RPC balances + "
            "Jupiter Price API v3 (see METRICS.md)"
        )
        if p.token_exposures:
            st.dataframe(
                pd.DataFrame(
                    list(p.token_exposures.items()),
                    columns=["Token", "Value (USD)"],
                )
            )
else:
    st.warning(
        "No wallets configured. Add `wallet_addresses` to `.config.yaml` "
        "(read-only public keys), then run the daemon."
    )

st.markdown("---")
st.markdown("Use the sidebar to navigate to Trade, Positions, and Alerts pages.")
