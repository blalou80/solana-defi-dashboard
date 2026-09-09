import streamlit as st
import uuid
from src.state import get_state
from src.models import Alert

st.set_page_config(page_title="Alert Configuration", layout="wide")

st.title("Alert Configuration")

# Display existing alerts
state = get_state()
alerts = state.alerts

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
    st.info("No alerts configured.")

# Add new alert
st.subheader("Add New Alert")
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
    from src.risk.alerts import send_alert
    import asyncio
    result = asyncio.run(send_alert("Test alert from dashboard", "telegram"))
    if result:
        st.success("Test alert sent!")
    else:
        st.error("Failed to send alert. Check webhook URLs.")