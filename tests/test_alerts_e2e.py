"""End-to-end alert delivery test (Phase 3).

A local HTTP sink stands in for the Telegram/Discord webhook (the wire
protocol is identical: POST JSON, expect 2xx). Proves the full chain:
config alert definition -> live Jupiter price -> threshold check ->
webhook POST -> delivered=1 persisted in alerts_log -> cooldown suppresses
the duplicate on the next cycle.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import src.risk.alerts as alerts_mod
from src.db import get_connection, last_alert_ts
from src.risk.alerts import process_alerts

_received = []


class _Sink(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        _received.append(json.loads(self.rfile.read(length)))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):  # silence
        pass


@pytest.fixture
def sink():
    _received.clear()
    srv = HTTPServer(("127.0.0.1", 0), _Sink)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture
def conn(tmp_path):
    c = get_connection(str(tmp_path / "alerts.db"))
    yield c
    c.close()


@pytest.mark.asyncio
async def test_stop_loss_fires_delivers_and_cooldowns(conn, sink, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", sink)

    # config-driven alert whose threshold is ABOVE the real SOL price
    # (SOL ~ $123; threshold 99999 must trigger a genuine stop-loss)
    class _Cfg:
        alerts = [{
            "type": "stop_loss", "symbol": "SOL", "threshold": 99999,
            "channel": "telegram", "enabled": True,
            "message_template": "{symbol} at {price} <= {threshold}",
        }]
        alert_cooldown_minutes = 30

    monkeypatch.setattr(alerts_mod, "load_config", lambda *a, **k: _Cfg())

    await process_alerts(conn)
    assert len(_received) == 1, "webhook sink must receive exactly one POST"
    assert "SOL at" in _received[0]["text"]
    row = conn.execute(
        "SELECT type, delivered FROM alerts_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert (row["type"], row["delivered"]) == ("stop_loss", 1)

    # second cycle inside the cooldown window must NOT re-fire
    await process_alerts(conn)
    assert len(_received) == 1, "cooldown violated: alert re-fired"

    # and the target is recorded for audit
    assert last_alert_ts(conn, "stop_loss", "stop_loss:SOL") is not None


@pytest.mark.asyncio
async def test_boundary_alert_from_persisted_position(conn, sink, monkeypatch):
    """An out-of-range position row in the DB (live ticks) fires boundary
    alerts with cooldown, exactly like the stop-loss path."""
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", sink)

    class _Cfg:
        alerts = [{
            "type": "boundary", "symbol": "SOL", "threshold": 0,
            "channel": "telegram", "enabled": True,
        }]
        alert_cooldown_minutes = 30

    monkeypatch.setattr(alerts_mod, "load_config", lambda *a, **k: _Cfg())
    from src.db import record_positions
    from src.models import CLPosition

    pos = CLPosition(
        position_id="TestPosOutOfRange111111111111111111111111111111",
        dex_name="Orca", pool_address="pool", token_a="SOL", token_b="USDC",
        tick_lower=-100, tick_upper=-50, current_tick=500, liquidity=1.0,
        is_in_range=False,
    )
    record_positions(conn, [pos], source="test-fixture")

    await process_alerts(conn)
    assert len(_received) == 1
    assert "out of range" in _received[0]["text"]

    await process_alerts(conn)
    assert len(_received) == 1, "boundary cooldown violated"
