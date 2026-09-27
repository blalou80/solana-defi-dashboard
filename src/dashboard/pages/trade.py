import asyncio

import pandas as pd
import streamlit as st

from src.config import load_config
from src.db import conn_for, list_quotes, list_watchlist, record_quote
from src.engines.slippage import (
    compute_slippage_metrics,
    get_quote,
    realized_slippage_from_tx,
)

st.set_page_config(page_title="Trade Slippage Analysis", layout="wide")

st.title("Real-Time Slippage Analysis")

st.markdown(
    "Live route quote from Jupiter Swap API v1. Every quote shown here is "
    "persisted to the `quotes` table so its numbers stay auditable."
)

RPC = "https://api.mainnet-beta.solana.com"
try:
    _cfg = load_config()
except Exception:
    _cfg = None
conn = conn_for(_cfg)

watched = list_watchlist(conn)
col1, col2, col3, col4 = st.columns(4)
with col1:
    token_in = st.text_input(
        "Token In (mint address)",
        "So11111111111111111111111111111111111111112",
    )
with col2:
    token_out = st.text_input(
        "Token Out (mint address)",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    )
with col3:
    amount = st.number_input(
        "Amount (in natural units)", min_value=0.0, value=1.0, step=0.1
    )
with col4:
    quote_wallet = st.selectbox(
        "Quote for wallet (optional)",
        [""] + [w["wallet"] for w in watched],
        format_func=lambda w: "— anonymous —" if w == "" else (w[:8] + "…" + w[-4:]),
        help="S4: attributes the logged quote to a watched wallet.",
    )

if st.button("Get Quote"):
    with st.spinner("Fetching quote..."):
        try:
            quote = asyncio.run(get_quote(token_in, token_out, amount))
            df = compute_slippage_metrics(quote)
            try:
                record_quote(conn, quote, wallet=quote_wallet or None)
            except Exception as e:
                st.warning(f"Quote shown, but logging failed: {e}")
            if df.empty:
                st.warning("No routes found.")
            else:
                st.success("Quote fetched successfully!")
                st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"Error fetching quote: {e}")

st.markdown("---")

# --- W4: realized slippage on a swap the user actually made ---------------
st.subheader("Check a swap I made")
st.caption(
    "Parses the real on-chain receipt (pre/postTokenBalances) for your "
    "transaction and compares what you received against what the quote "
    "promised. No simulation."
)
with st.form("check_swap", clear_on_submit=True):
    sc1, sc2 = st.columns(2)
    with sc1:
        sig = st.text_input("Transaction signature")
        wallet = st.text_input("Your wallet address")
    with sc2:
        expected_out = st.number_input(
            "Expected output (natural units, from the quote)",
            min_value=0.0,
            value=0.0,
            step=0.1,
        )
        out_mint = st.text_input("Output token mint", "")
    if st.form_submit_button("Compute realized slippage"):
        if not (sig.strip() and wallet.strip() and out_mint.strip()
                and expected_out > 0):
            st.error("Signature, wallet, output mint and expected amount are all required.")
        else:
            try:
                slip = asyncio.run(
                    realized_slippage_from_tx(
                        sig.strip(), wallet.strip(), float(expected_out),
                        out_mint.strip(), RPC,
                    )
                )
            except Exception as e:
                slip = None
                st.error(f"Receipt fetch failed: {e}")
            if slip is not None:
                tone = "success" if slip <= 0.5 else "warning"
                getattr(st, tone)(
                    f"Realized slippage: **{slip:.3f}%** "
                    f"(positive = you received less than expected)"
                )
            elif slip is None:
                st.info(
                    "Unavailable: the receipt contains no movement of that "
                    "mint for that wallet. Nothing is estimated."
                )

st.markdown("---")
st.subheader("Quote log (this machine)")
qrows = list_quotes(conn, limit=25)
if qrows:
    dfq = pd.DataFrame(qrows)
    dfq["route_labels"] = dfq["route_labels"].astype(str).str.slice(0, 40)
    st.dataframe(
        dfq[["ts", "input_mint", "output_mint", "out_amount",
             "price_impact_pct", "slippage_bps", "route_labels"]],
        use_container_width=True,
    )
else:
    st.info("No quotes logged yet — run Get Quote above.")
