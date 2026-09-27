"""Webhook alert system for Telegram and Discord.

Phase-0 honesty pass: the old stop-loss check compared thresholds against
a hardcoded mock price of 100. Now prices come from the live Jupiter
Price API; when a price is unavailable the alert is skipped and logged,
never evaluated against a made-up number. Fired alerts are persisted to
the SQLite alerts_log so both processes share one history.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiohttp

from ..config import load_config
from ..db import (
    last_alert_ts,
    latest_positions,
    latest_snapshot,
    list_alert_rules,
    log_alert,
)
from ..models import Alert
from ..services.market_data import KNOWN_TOKENS, get_usd_prices

logger = logging.getLogger(__name__)

# symbol -> mint, for stop-loss price lookups (seed; registry extends it)
_SYMBOL_MINT = {sym: mint for mint, (sym, _dec) in KNOWN_TOKENS.items()}

# minutes between repeat alerts for the same (type, target)
DEFAULT_COOLDOWN_MIN = 30


def _resolve_mint(symbol: Optional[str], conn=None) -> Optional[str]:
    """Seed map first, then the SQLite token registry (W2). Unknown symbol
    returns None — the alert is skipped, never priced against a guess."""
    if not symbol:
        return None
    mint = _SYMBOL_MINT.get(symbol)
    if mint or conn is None:
        return mint
    from ..db import find_mint_by_symbol

    return find_mint_by_symbol(conn, symbol)


def _in_cooldown(conn, type_: str, target: str, cooldown_min: int) -> bool:
    if conn is None:
        return False
    ts = last_alert_ts(conn, type_, target)
    if ts is None:
        return False
    age_min = (
        datetime.now(timezone.utc) - datetime.fromisoformat(ts)
    ).total_seconds() / 60
    return age_min < cooldown_min


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
        async with aiohttp.ClientSession() as session, session.post(
            url, json=payload
        ) as resp:
            if 200 <= resp.status < 300:
                logger.info(f"Alert sent to {channel}")
                return True
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


async def _live_prices_for(alerts: List[Alert], conn=None) -> Dict[str, Optional[float]]:
    """Fetch real USD prices for every symbol referenced by stop-loss alerts."""
    mints = set()
    for a in alerts:
        if a.enabled and a.type == "stop_loss":
            mint = _resolve_mint(a.threshold_symbol, conn)
            if mint:
                mints.add(mint)
    if not mints:
        return {}
    try:
        prices = await get_usd_prices(sorted(mints))
    except Exception as e:
        logger.error(f"Price fetch failed; stop-loss checks skipped this cycle: {e}")
        return {}
    return {
        mint: prices.get(mint) for mint in mints
    }


async def process_alerts(conn=None) -> None:
    """Check alert conditions against real data and dispatch notifications.

    W4: alert definitions are durable — they come from the ``alert_rules``
    SQLite table (managed in the dashboard) plus ``.config.yaml``
    (headless setups). The in-process session alerts are retired.
    Boundary checks read only the persisted positions table (live pool
    ticks from the daemon). Nothing is evaluated against mock prices, and
    each rule's own cooldown window is honored per (type, target).
    """
    config = load_config()
    default_cooldown = int(
        getattr(config, "alert_cooldown_minutes", DEFAULT_COOLDOWN_MIN)
    )
    definitions: List[tuple] = []  # (Alert, cooldown_min)
    for raw in getattr(config, "alerts", []) or []:
        definitions.append(
            (
                Alert(
                    id=f"cfg-{raw.get('symbol', 'unknown')}-{raw.get('threshold')}",
                    type=raw.get("type", "stop_loss"),
                    threshold=float(raw.get("threshold", 0)),
                    channel=raw.get("channel", "telegram"),
                    message_template=raw.get(
                        "message_template", "{symbol} hit {threshold} (now {price})"
                    ),
                    enabled=bool(raw.get("enabled", True)),
                    threshold_symbol=raw.get("symbol"),
                    wallet=raw.get("wallet"),
                ),
                default_cooldown,
            )
        )
    if conn is not None:
        for rule in list_alert_rules(conn):
            definitions.append(
                (
                    Alert(
                        id=f"rule-{rule['id']}",
                        type=rule["type"],
                        threshold=float(rule["threshold"] or 0),
                        channel=rule["channel"],
                        message_template=rule["message_template"]
                        or "{symbol} hit {threshold} (now {price})",
                        enabled=bool(rule["enabled"]),
                        threshold_symbol=rule["symbol"],
                        wallet=rule.get("wallet"),
                    ),
                    int(rule["cooldown_min"]),
                )
            )

    fired_any = False

    for alert, cooldown in definitions:
        if not alert.enabled:
            continue
        if alert.type == "stop_loss":
            scope = f"{alert.wallet[:8]}:" if alert.wallet else ""
            target = f"stop_loss:{scope}{alert.threshold_symbol}"
            if _in_cooldown(conn, "stop_loss", target, cooldown):
                continue
            # S4 wallet scope: a wallet-bound stop_loss only fires while
            # that wallet's latest real snapshot actually holds the symbol.
            if alert.wallet and conn is not None:
                snap = latest_snapshot(conn, alert.wallet)
                held = snap and any(
                    (b.get("symbol") or "").upper()
                    == (alert.threshold_symbol or "").upper()
                    for b in snap["balances"]
                )
                if not held:
                    logger.info(
                        f"Stop-loss '{alert.id}' skipped: scoped wallet holds "
                        f"no {alert.threshold_symbol} in its latest snapshot."
                    )
                    continue
            mint = _resolve_mint(alert.threshold_symbol, conn)
            prices = await _live_prices_for([alert], conn)
            price = prices.get(mint) if mint else None
            if price is None:
                logger.warning(
                    f"Stop-loss '{alert.id}': no live price for "
                    f"{alert.threshold_symbol!r} — skipped (never checked "
                    "against a mock price)."
                )
                if conn is not None:
                    log_alert(
                        conn,
                        "stop_loss_skipped",
                        f"No live price for {alert.threshold_symbol}; check skipped.",
                        alert.channel,
                        target=target,
                    )
                continue
            if check_stop_loss(alert.threshold, price):
                message = alert.message_template.format(
                    symbol=alert.threshold_symbol, threshold=alert.threshold, price=price
                )
                delivered = await send_alert(message, alert.channel)
                if conn is not None:
                    log_alert(
                        conn, "stop_loss", message, alert.channel,
                        delivered, target=target,
                    )
                fired_any = True
        elif alert.type == "boundary":
            # positions table = live-tick monitored CL positions (daemon)
            rows: List[Dict] = []
            if conn is not None:
                rows = [
                    p
                    for p in latest_positions(conn)
                    if not p["is_in_range"]
                    and (alert.wallet is None or p.get("wallet") == alert.wallet)
                ]
            for p in rows:
                pid = p["position_id"]
                target = f"boundary:{pid}"
                if _in_cooldown(conn, "boundary", target, cooldown):
                    continue
                message = (
                    f"Position {pid} out of range! "
                    f"tick {p.get('current_tick')} vs "
                    f"[{p.get('tick_lower')}, {p.get('tick_upper')}]"
                )
                delivered = await send_alert(message, alert.channel)
                if conn is not None:
                    log_alert(
                        conn, "boundary", message, alert.channel,
                        delivered, target=target,
                    )
                fired_any = True

    if not definitions:
        logger.debug("No alert definitions configured; nothing to check.")
    if fired_any:
        logger.info("Alert processing complete: at least one alert fired.")
