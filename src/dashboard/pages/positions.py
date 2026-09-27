import pandas as pd
import streamlit as st

from src.config import load_config
from src.db import get_connection, latest_positions

st.set_page_config(page_title="Liquidity Positions", layout="wide")

st.title("Concentrated Liquidity Positions")

# Positions come from the shared SQLite store, populated by the daemon via
# the Orca Whirlpool API (source column carries provenance; see METRICS.md).
try:
    config = load_config()
    conn = get_connection(config.db_path)
    rows = latest_positions(conn)
except Exception as e:
    st.error(f"Could not read position store: {e}")
    rows = []

if rows:
    df = pd.DataFrame(rows)
    show = df[[
        "position_id", "dex_name", "token_a", "token_b", "tick_lower",
        "tick_upper", "current_tick", "is_in_range", "liquidity",
        "fees_owed_a", "fees_owed_b", "ts", "source",
    ]].copy()
    show["position_id"] = show["position_id"].str.slice(0, 10) + "…"
    st.dataframe(show, use_container_width=True)
    out_of_range = df[~df["is_in_range"].astype(bool)]
    if len(out_of_range):
        st.warning(
            f"{len(out_of_range)} position(s) are OUT OF RANGE "
            "(live pool tick vs. position bounds)."
        )
    else:
        st.success("All tracked positions are in range (live ticks).")
    st.caption(
        "current_tick = pool tickCurrentIndex at fetch time · range = "
        "tick_lower ≤ current_tick ≤ tick_upper · source column = data origin"
    )
else:
    st.info(
        "No positions stored yet. The daemon ingests Orca Whirlpool "
        "positions for every `wallet_addresses` entry each tick; wallets "
        "without CL positions legitimately show nothing here. No mock "
        "positions are ever displayed."
    )
