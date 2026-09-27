import altair as alt
import pandas as pd
import streamlit as st

from src.config import load_config
from src.db import get_connection, latest_positions, position_history
from src.risk.metrics import position_impermanent_loss

st.set_page_config(page_title="Liquidity Positions", layout="wide")

st.title("Concentrated Liquidity Positions")

# Positions come from the shared SQLite store, populated by the daemon via
# the Orca Whirlpool API (source column carries provenance; see METRICS.md).
# Every tick appends a row, so the same table doubles as 7-day history.
# Rendering lives in a function because st.stop() is a no-op outside the
# Streamlit runtime (import smoke tests) — an early return is the only
# guard that works in both modes.
try:
    config = load_config()
    conn = get_connection(config.db_path)
    rows = latest_positions(conn)
except Exception as e:
    st.error(f"Could not read position store: {e}")
    rows = []


def _render(rows):
    interval = getattr(config, "polling_interval_sec", 15) if config else 15
    df = pd.DataFrame(rows)
    out_of_range = df[~df["is_in_range"].astype(bool)]
    if len(out_of_range):
        st.warning(
            f"{len(out_of_range)} position(s) are OUT OF RANGE "
            "(live pool tick vs. position bounds)."
        )
    else:
        st.success("All tracked positions are in range (live ticks).")

    for p in rows:
        st.subheader(
            f"`{p['position_id'][:10]}…` — {p['token_a']}/{p['token_b']} "
            f"({p['dex_name']})"
        )
        hist = pd.DataFrame(position_history(conn, p["position_id"]))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Range status", "IN RANGE" if p["is_in_range"] else "OUT OF RANGE")
        c2.metric("Pool tick", f"{p['current_tick']:,}")
        il = (
            position_impermanent_loss(hist.to_dict("records")) if len(hist) else None
        )
        c3.metric(
            "IL since first observation",
            "unavailable" if il is None else f"{il:.2f}%",
            help=(
                "Entry-price proxy = pool price at the earliest stored tick "
                "(daemon cannot know the true on-chain entry). "
                f"{len(hist)} observations."
            ),
        )
        oor_n = int((~hist["is_in_range"].astype(bool)).sum()) if len(hist) else 0
        c4.metric(
            "Time out of range (approx)",
            f"{oor_n * interval / 60:.0f} min",
            help=f"out-of-range observations × {interval}s polling interval",
        )

        if len(hist) >= 2:
            hist["ts_dt"] = pd.to_datetime(hist["ts"], utc=True, format="mixed")
            left, right = st.columns(2)
            with left:
                st.caption("Pool tick vs. position bounds")
                band = (
                    alt.Chart(hist)
                    .mark_line(color="#9945ff")
                    .encode(
                        x=alt.X("ts_dt:T", title=None),
                        y=alt.Y("current_tick:Q", title="tick"),
                        tooltip=["ts", "current_tick"],
                    )
                    + alt.Chart(hist)
                    .mark_rule(color="#4ade80", strokeDash=[4, 4])
                    .encode(y="min(tick_lower):Q")
                    + alt.Chart(hist)
                    .mark_rule(color="#f87171", strokeDash=[4, 4])
                    .encode(y="max(tick_upper):Q")
                )
                st.altair_chart(band, use_container_width=True)
            with right:
                hist["fees_total"] = (
                    hist["fees_owed_a"].fillna(0) + hist["fees_owed_b"].fillna(0)
                )
                st.caption("Accrued fees (token A + B, raw amounts)")
                st.altair_chart(
                    alt.Chart(hist)
                    .mark_area(line={"color": "#9945ff"}, color="#9945ff22")
                    .encode(
                        x=alt.X("ts_dt:T", title=None),
                        y=alt.Y("fees_total:Q", title="fees"),
                        tooltip=["ts", "fees_owed_a", "fees_owed_b"],
                    ),
                    use_container_width=True,
                )
        else:
            st.caption("Collecting history — charts appear after the second tick.")

    st.caption(
        "current_tick = pool tickCurrentIndex at fetch time · bounds/fees = "
        "Orca v2 API · history pruned to 7 days · see METRICS.md for provenance"
    )


if rows:
    _render(rows)
else:
    st.info(
        "No positions stored yet. The daemon ingests Orca Whirlpool "
        "positions for every watched wallet each tick; wallets without CL "
        "positions legitimately show nothing here. No mock positions are "
        "ever displayed."
    )
