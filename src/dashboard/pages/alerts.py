import uuid

import streamlit as st

from src.config import load_config
from src.db import get_connection
from src.models import Alert
from src.state import get_state

st.set_page_config(page_title="Alert Configuration", layout="wide")

st.title("Alert Configuration")

# Definitions from .config.yaml (shared across processes) + session-added
state = get_state()
alerts = list(state.alerts)
try:
    config = load_config()
    for raw in getattr(config, "alerts", []) or []:
        alerts.append(
            Alert(
                id=f"cfg-{raw.get('symbol', '?')}-{raw.get('threshold')}",
                type=raw.get("type", "stop_loss"),
                threshold=float(raw.get("threshold", 0)),
                channel=raw.get("channel", "telegram"),
                message_template=raw.get("message_template", "Alert triggered!"),
                enabled=bool(raw.get("enabled", True)),
                threshold_symbol=raw.get("symbol"),
            )
        )
except Exception as e:
    st.warning(f"Could not load alert definitions from config: {e}")

st.subheader("Current Alerts")
if alerts:
    for alert in alerts:
        col1, col2, col3, col4 = st.columns([3,2,2,1])
        with col1:
            st.write(f"Type: {alert.type}")
        with col2:
            st.write(f"Threshold: {alert.threshold}")
        with col3:
            st.write(f"Channel: {alert.channel}")
        with col4:
            st.write("Enabled" if alert.enabled else "Disabled")
else:
    st.info(
        "No alerts configured. Add an `alerts:` list to `.config.yaml` "
        "(type: stop_loss, symbol: SOL, threshold: 100, channel: telegram) "
        "so the daemon can act on them."
    )

# Fired/skipped alert history, persisted by the daemon
try:
    conn = get_connection(config.db_path if config else None)
    log_rows = conn.execute(
        "SELECT ts, type, message, channel, delivered FROM alerts_log "
        "ORDER BY ts DESC LIMIT 100"
    ).fetchall()
    st.subheader("Alert Log (persisted)")
    if log_rows:
        import pandas as pd
        st.dataframe(pd.DataFrame([dict(r) for r in log_rows]), use_container_width=True)
    else:
        st.write("No alerts fired or skipped yet.")
except Exception as e:
    st.error(f"Could not read alert log: {e}")

# Add new alert (this session only — daemon acts on config-defined alerts)
st.subheader("Add New Alert (this dashboard session)")
with st.form("add_alert"):
    alert_type = st.selectbox("Alert Type", ["stop_loss", "boundary", "anomaly"])
    threshold = st.number_input("Threshold", value=0.0)
    channel = st.selectbox("Channel", ["telegram", "discord"])
    message = st.text_input("Message Template", "Alert triggered!")
    enabled = st.checkbox("Enabled", value=True)
    submitted = st.form_submit_button("Add Alert")
    if submitted:
        new_alert = Alert(
            id=str(uuid.uuid4()),
            type=alert_type,
            threshold=threshold,
            channel=channel,
            message_template=message,
            enabled=enabled
        )
        state.alerts.append(new_alert)
        st.success("Alert added!")

# Simulate alert trigger (for testing)
st.subheader("Test Alert")
if st.button("Send Test Alert"):
    # Use send_alert from risk.alerts
    import asyncio

    from src.risk.alerts import send_alert
    result = asyncio.run(send_alert("Test alert from dashboard", "telegram"))
    if result:
        st.success("Test alert sent!")
    else:
        st.error("Failed to send alert. Check webhook URLs.")
