"""W4 tests: durable alert rules (table-driven, daemon-consumed) and the
persisted quote log."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import src.risk.alerts as alerts_mod
from src.db import (
    add_alert_rule,
    delete_alert_rule,
    get_connection,
    list_alert_rules,
    list_quotes,
    record_quote,
)

_received = []


class _Sink(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        _received.append(json.loads(self.rfile.read(length)))
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
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
    c = get_connection(str(tmp_path / "w4.db"))
    yield c
    c.close()


# --- rules CRUD -------------------------------------------------------------

def test_rule_crud_roundtrip(conn):
    rid = add_alert_rule(conn, "stop_loss", "telegram", symbol="SOL",
                         threshold=100.0, cooldown_min=45)
    rules = list_alert_rules(conn)
    assert len(rules) == 1
    r = rules[0]
    assert r["id"] == rid and r["type"] == "stop_loss"
    assert r["symbol"] == "SOL" and r["cooldown_min"] == 45
    assert r["enabled"] == 1 and r["source"] == "ui"
    assert delete_alert_rule(conn, rid) is True
    assert list_alert_rules(conn) == []
    assert delete_alert_rule(conn, rid) is False


# --- daemon consumes the table ----------------------------------------------

class _EmptyCfg:
    alerts = []
    alert_cooldown_minutes = 30


@pytest.mark.asyncio
async def test_process_alerts_reads_rules_table(conn, sink, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", sink)
    monkeypatch.setattr(
        alerts_mod, "load_config", lambda *a, **k: _EmptyCfg()
    )
    # threshold far above the real SOL price -> must fire on live data
    add_alert_rule(conn, "stop_loss", "telegram", symbol="SOL",
                   threshold=99999, cooldown_min=30)

    await alerts_mod.process_alerts(conn)
    assert len(_received) == 1
    row = conn.execute(
        "SELECT type, delivered, target FROM alerts_log"
    ).fetchone()
    assert (row["type"], row["delivered"], row["target"]) == (
        "stop_loss", 1, "stop_loss:SOL",
    )

    # disabled rules never fire
    conn.execute("UPDATE alert_rules SET enabled = 0")
    conn.commit()
    await alerts_mod.process_alerts(conn)
    assert len(_received) == 1


@pytest.mark.asyncio
async def test_per_rule_cooldown_respected(conn, sink, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", sink)
    monkeypatch.setattr(
        alerts_mod, "load_config", lambda *a, **k: _EmptyCfg()
    )
    add_alert_rule(conn, "stop_loss", "telegram", symbol="SOL",
                   threshold=99999, cooldown_min=10)
    await alerts_mod.process_alerts(conn)
    await alerts_mod.process_alerts(conn)  # inside 10-min window
    assert len(_received) == 1


# --- quote log ---------------------------------------------------------------

V1_QUOTE = {
    "inputMint": "So11111111111111111111111111111111111111112",
    "inAmount": "1000000000",
    "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "outAmount": "122846032",
    "slippageBps": 50,
    "priceImpactPct": "0.0000062",
    "routePlan": [{"swapInfo": {"label": "Meteora DLMM"}, "percent": 100}],
}


def test_quote_roundtrip(conn):
    qid = record_quote(conn, V1_QUOTE)
    rows = list_quotes(conn)
    assert len(rows) == 1
    q = rows[0]
    assert q["id"] == qid
    assert q["out_amount"] == "122846032"
    assert q["slippage_bps"] == 50
    assert json.loads(q["route_labels"]) == ["Meteora DLMM"]


def test_quote_empty_plan_stored_honestly(conn):
    q = dict(V1_QUOTE, routePlan=[])
    record_quote(conn, q)
    row = list_quotes(conn)[0]
    assert json.loads(row["route_labels"]) == []
    assert row["out_amount"] == "122846032"
