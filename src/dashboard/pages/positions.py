import streamlit as st
import pandas as pd
from src.state import get_state

st.set_page_config(page_title="Liquidity Positions", layout="wide")

st.title("Concentrated Liquidity Positions")

state = get_state()
positions = state.positions

if positions:
    # Convert to DataFrame for display
    data = [{
        "ID": p.id[:8],
        "Pool": p.pool_id[:8],
        "Owner": p.owner[:8],
        "Tick Lower": p.tick_lower,
        "Tick Upper": p.tick_upper,
        "Current Tick": p.current_tick,
        "Liquidity": p.liquidity,
        "Fees Earned": p.fees_earned,
        "Impermanent Loss": p.impermanent_loss,
        "Net Yield %": p.net_yield
    } for p in positions]
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)

    # Show out-of-range positions
    out_of_range = [p for p in positions if p.current_tick < p.tick_lower or p.current_tick > p.tick_upper]
    if out_of_range:
        st.warning(f"{len(out_of_range)} positions are out of range!")
        for p in out_of_range:
            st.write(f"Position {p.id[:8]} is out of range (current tick {p.current_tick}, range {p.tick_lower}-{p.tick_upper})")
    else:
        st.success("All positions are in range.")
else:
    st.info("No positions being tracked. Add positions to the configuration.")