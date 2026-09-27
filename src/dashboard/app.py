import pandas as pd
import streamlit as st

from src.config import load_config
from src.db import add_watch, conn_for, list_watchlist, remove_watch
from src.risk.metrics import compute_portfolio_metrics
from src.utils import setup_logging
from src.validation import validate_solana_address

# Setup logging
setup_logging()

st.set_page_config(page_title="Solana DeFi Analytics", layout="wide")

st.title("Solana DeFi Analytics & Risk Management Dashboard")

# Sidebar for config info
st.sidebar.header("Configuration")
config = None
try:
    config = load_config()
    st.sidebar.write(f"RPC: {config.rpc_endpoint[:30]}...")
    st.sidebar.write(f"Polling interval: {config.polling_interval_sec}s")
    st.sidebar.write(f"Risk window: {config.risk_window_days} days")
except Exception as e:
    st.sidebar.error(f"Error loading config: {e}")

conn = conn_for(config)

# --- Watch a wallet (W1 onboarding) -------------------------------------
st.header("Watch a wallet")
with st.form("add_wallet", clear_on_submit=True):
    col_a, col_b = st.columns([3, 1])
    with col_a:
        wallet_input = st.text_input(
            "Solana wallet address (public key, read-only)",
            placeholder="e.g. 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        )
    with col_b:
        label_input = st.text_input("Label (optional)", placeholder="cold wallet")
    submitted = st.form_submit_button("Add to watchlist")
    if submitted:
        ok, result = validate_solana_address(wallet_input)
        if not ok:
            st.error(f"Invalid address: {result}")
        else:
            added = add_watch(conn, result, label_input.strip() or None, source="ui")
            st.success(
                f"Watching `{result[:8]}…{result[-4:]}` — the daemon picks it up "
                "on its next tick."
                if added
                else f"`{result[:8]}…` is already on the watchlist."
            )

watched = list_watchlist(conn)
if watched:
    st.subheader("Watchlist")
    for w in watched:
        cols = st.columns([4, 1, 1, 1])
        cols[0].write(
            f"`{w['wallet'][:8]}…{w['wallet'][-4:]}`"
            + (f" — {w['label']}" if w["label"] else "")
            + f"  ·  added via {w['source']}"
        )
        cols[1].caption(w["added_ts"][:19])
        if w["source"] == "ui" and cols[2].button("Remove", key=f"rm_{w['wallet']}"):
            remove_watch(conn, w["wallet"])
            st.rerun()
        if w["source"] == "config":
            cols[2].caption("(from .config.yaml)")

# --- Portfolio summary ---------------------------------------------------
# Data comes from the SQLite store written by the daemon
# (python -m src.main). Nothing on this page is ever mock data; missing
# data renders as an explicit unavailable state.
st.header("Portfolio Summary")

wallets = [w["wallet"] for w in watched]
for w in (config.wallet_addresses if config else []):
    if w not in wallets:
        wallets.append(w)

if wallets:
    for wallet in wallets:
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
                help="From snapshot returns; needs ≥ 5 samples.",
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
        "No wallets to show. Add one above (or set `wallet_addresses` in "
        "`.config.yaml`), then run the daemon to collect real data."
    )

st.markdown("---")
st.markdown("Use the sidebar to navigate to Trade, Positions, and Alerts pages.")
