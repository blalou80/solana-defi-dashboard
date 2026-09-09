"""Webhook alert system for Telegram and Discord."""

import aiohttp
import logging
import os
from typing import Optional
from ..config import load_config
from ..models import Alert
from ..state import get_state

logger = logging.getLogger(__name__)

async def send_alert(message: str, channel: str) -> bool:
    """Send an alert to Telegram or Discord via webhook. Returns True on success."""
    if channel.lower() == "telegram":
        url = os.getenv("TELEGRAM_WEBHOOK_URL")
        if not url:
            logger.error("TELEGRAM_WEBHOOK_URL not set")
            return False
        payload = {"text": message}
    elif channel.lower() == "discord":
        url = os.getenv("DISCORD_WEBHOOK_URL")
        if not url:
            logger.error("DISCORD_WEBHOOK_URL not set")
            return False
        payload = {"content": message}
    else:
        logger.error(f"Unsupported channel: {channel}")
        return False

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status >= 200 and resp.status < 300:
                    logger.info(f"Alert sent to {channel}")
                    return True
                else:
                    text = await resp.text()
                    logger.error(f"Failed to send alert to {channel}: {resp.status} {text}")
                    return False
    except Exception as e:
        logger.error(f"Error sending alert: {e}")
        return False

def check_stop_loss(threshold: float, current_price: float) -> bool:
    """Check if stop-loss should trigger."""
    return current_price <= threshold

def check_boundary_alert(position) -> bool:
    """Check if position is out of range."""
    from ..engines.liquidity import check_boundary
    return check_boundary(position.current_tick, position.tick_lower, position.tick_upper)

async def process_alerts() -> None:
    """Periodically check alert conditions and send notifications."""
    state = get_state()
    for alert in state.alerts:
        if not alert.enabled:
            continue
        if alert.type == "stop_loss":
            if check_stop_loss(alert.threshold, 100):  # mock price
                await send_alert(alert.message_template, alert.channel)
        elif alert.type == "boundary":
            for pos in state.positions:
                if check_boundary_alert(pos):
                    await send_alert(f"Position {pos.id} out of range!", alert.channel)
    logger.info("Alert processing complete.")