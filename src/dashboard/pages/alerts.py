import asyncio

import pandas as pd
import streamlit as st

from src.config import load_config
from src.db import (
    add_alert_rule,
    conn_for,
    delete_alert_rule,
    list_alert_rules,
)

st.set_page_config(page_title="Alert Rules", layout="wide")

st.title("Alert Rules")

# W4: rules are durable — stored in the shared SQLite `alert_rules` table,
# read by the daemon every tick. The old session-only form is retired:
# anything added here survives restarts and works across processes.
config = None
try:
    config = load_config()
except Exception as e:
    st.warning(f"Could not load config (headless alerts still work): {e}")

conn = conn_for(config)

# --- create rule ----------------------------------------------------------
st.subheader("Add a rule")
with st.form("add_rule", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        rule_type = st.selectbox(
            "Type", ["stop_loss", "boundary"],
            help="stop_loss: fires when a live USD price <= threshold. "
                 "boundary: fires for any watched CL position out of range.",
        )
        symbol = st.text_input(
            "Symbol (stop_loss only)",
            value="SOL",
            help="Resolved via the token registry cache; unknown symbols "
                 "are skipped with a logged reason, never guessed.",
        )
    with c2:
        threshold = st.number_input(
            "Threshold USD (stop_loss only)", value=0.0, step=1.0
        )
        channel = st.selectbox("Channel", ["telegram", "discord"])
    with c3:
        cooldown = st.number_input(
            "Cooldown (minutes)", value=30, min_value=1, step=5,
            help="Minimum gap between repeat alerts for the same target.",
        )
        enabled = st.checkbox("Enabled", value=True)
    if st.form_submit_button("Save rule"):
        if rule_type == "stop_loss" and not symbol.strip():
            st.error("stop_loss needs a symbol.")
        else:
            rid = add_alert_rule(
                conn,
                rule_type,
                channel,
                symbol=symbol.strip() or None,
                threshold=threshold if rule_type == "stop_loss" else None,
                enabled=enabled,
                cooldown_min=int(cooldown),
                source="ui",
            )
            st.success(f"Rule #{rid} saved — active from the daemon's next tick.")

# --- current rules ---------------------------------------------------------
rules = list_alert_rules(conn)
st.subheader("Durable rules")
if rules:
    for r in rules:
        cols = st.columns([5, 1, 1, 1])
        cols[0].write(
            f"#{r['id']} · {r['type']}"
            + (f" {r['symbol']}" if r["symbol"] else "")
            + (f" ≤ {r['threshold']}" if r["threshold"] is not None else "")
            + f" → {r['channel']} · cooldown {r['cooldown_min']}min"
            + ("" if r["enabled"] else " · DISABLED")
        )
        cols[1].caption(r["created_ts"][:19])
        cols[2].caption(r["source"])
        if cols[3].button("Delete", key=f"del_rule_{r['id']}"):
            delete_alert_rule(conn, r["id"])
            st.rerun()
else:
    st.info("No durable rules yet. Add one above, or define `alerts:` in .config.yaml.")

cfg_alerts = (getattr(config, "alerts", []) or []) if config else []
if cfg_alerts:
    st.caption(
        f"Plus {len(cfg_alerts)} rule(s) from .config.yaml (edit the file to change)."
    )

# --- fired/skipped history --------------------------------------------------
try:
    log_rows = conn.execute(
        "SELECT ts, type, message, channel, target, delivered FROM alerts_log "
        "ORDER BY ts DESC LIMIT 100"
    ).fetchall()
    st.subheader("Alert log (persisted)")
    if log_rows:
        st.dataframe(
            pd.DataFrame([dict(r) for r in log_rows]), use_container_width=True
        )
    else:
        st.write("No alerts fired or skipped yet.")
except Exception as e:
    st.error(f"Could not read alert log: {e}")

# --- webhook sanity check ----------------------------------------------------
st.subheader("Test webhook")
if st.button("Send test alert to Telegram webhook"):
    from src.risk.alerts import send_alert

    result = asyncio.run(
        send_alert("Test alert from dashboard", "telegram")
    )
    if result:
        st.success("Test alert delivered (webhook returned 2xx).")
    else:
        st.error(
            "Not delivered — check TELEGRAM_WEBHOOK_URL in .env. "
            "Failures are never reported as success."
        )
