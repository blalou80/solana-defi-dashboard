"""S4 tests: wallet-scoped alert rules, position ownership, quote attribution."""

import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import src.risk.alerts as alerts_mod
from src.db import (
    add_alert_rule,
    get_connection,
    list_quotes,
    record_positions,
    record_quote,
    record_snapshot,
)
from src.models import CLPosition

WALLET_A = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
WALLET_B = "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs"

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
    c = get_connection(str(tmp_path / "s4.db"))
    yield c
    c.close()


class _Cfg:
    alerts = []
    alert_cooldown_minutes = 30
    db_path = None


def _pos(pid, wallet_tag):
    return CLPosition(
        position_id=pid, dex_name="Orca", pool_address="p",
        token_a="SOL", token_b=f"T{wallet_tag}", tick_lower=-100,
        tick_upper=-50, current_tick=500, liquidity=1.0, is_in_range=False,
    )


# --- migration -------------------------------------------------------------

def test_migration_adds_wallet_columns_to_old_db(tmp_path):
    old = str(tmp_path / "old.db")
    c = sqlite3.connect(old)
    c.executescript(
        """CREATE TABLE alert_rules (id INTEGER PRIMARY KEY AUTOINCREMENT,
           type TEXT, symbol TEXT, threshold REAL, channel TEXT,
           message_template TEXT, enabled INTEGER, cooldown_min INTEGER,
           created_ts TEXT, source TEXT);
           CREATE TABLE quotes (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT,
           input_mint TEXT, output_mint TEXT, in_amount TEXT, out_amount TEXT,
           price_impact_pct REAL, slippage_bps INTEGER, route_labels TEXT,
           source TEXT);
           CREATE TABLE positions (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT,
           position_id TEXT, dex_name TEXT, pool_address TEXT, token_a TEXT,
           token_b TEXT, tick_lower INTEGER, tick_upper INTEGER,
           current_tick INTEGER, liquidity REAL, fees_owed_a REAL,
           fees_owed_b REAL, impermanent_loss REAL, is_in_range INTEGER,
           source TEXT, UNIQUE (ts, position_id));"""
    )
    c.commit()
    c.close()
    migrated = get_connection(old)  # must not raise, must add columns
    for table in ("alert_rules", "quotes", "positions"):
        cols = {r[1] for r in migrated.execute(f"PRAGMA table_info({table})")}
        assert "wallet" in cols, table
    migrated.close()


# --- boundary scoping --------------------------------------------------------

@pytest.mark.asyncio
async def test_boundary_rule_only_fires_for_its_wallet(conn, sink, monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", sink)
    monkeypatch.setattr(alerts_mod, "load_config", lambda *a, **k: _Cfg())
    record_positions(conn, [_pos("PosA111111", "A")], source="t", wallet=WALLET_A)
    record_positions(conn, [_pos("PosB111111", "B")], source="t", wallet=WALLET_B)
    add_alert_rule(conn, "boundary", "telegram", cooldown_min=30,
                   wallet=WALLET_A)

    await alerts_mod.process_alerts(conn)
    assert len(_received) == 1
    assert "PosA111111" in _received[0]["text"]
    assert "PosB111111" not in _received[0]["text"]

    # an unscoped rule now also catches wallet B's position (A is in cooldown)
    add_alert_rule(conn, "boundary", "telegram", cooldown_min=30, wallet=None)
    await alerts_mod.process_alerts(conn)
    assert len(_received) == 2
    assert "PosB111111" in _received[1]["text"]


# --- stop_loss holding check ---------------------------------------------------

@pytest.mark.asyncio
async def test_scoped_stop_loss_requires_wallet_to_hold_symbol(
    conn, sink, monkeypatch
):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", sink)
    monkeypatch.setattr(alerts_mod, "load_config", lambda *a, **k: _Cfg())
    record_snapshot(conn, WALLET_A, [
        {"mint": "So11111111111111111111111111111111111111112",
         "symbol": "SOL", "amount": 1.0, "usd_price": 120.0, "usd_value": 120.0},
    ], source="t")
    record_snapshot(conn, WALLET_B, [
        {"mint": "USDCMINT", "symbol": "USDC", "amount": 5.0,
         "usd_price": 1.0, "usd_value": 5.0},
    ], source="t")
    # threshold above live SOL price -> would fire if scope allowed
    add_alert_rule(conn, "stop_loss", "telegram", symbol="SOL",
                   threshold=99999, wallet=WALLET_B)  # B holds no SOL
    await alerts_mod.process_alerts(conn)
    assert len(_received) == 0  # scoped out: never even priced

    add_alert_rule(conn, "stop_loss", "telegram", symbol="SOL",
                   threshold=99999, wallet=WALLET_A)  # A holds SOL
    await alerts_mod.process_alerts(conn)
    assert len(_received) == 1


# --- quote attribution + position ownership ------------------------------------

QUOTE = {
    "inputMint": "So11111111111111111111111111111111111111112",
    "inAmount": "1", "outputMint": "EPjF", "outAmount": "2",
    "priceImpactPct": "0", "slippageBps": 50, "routePlan": [],
}


def test_quote_and_position_ownership_roundtrip(conn):
    record_quote(conn, QUOTE, wallet=WALLET_A)
    q = list_quotes(conn)[0]
    assert q["wallet"] == WALLET_A
    record_positions(conn, [_pos("Own1", "A")], source="t", wallet=WALLET_A)
    row = conn.execute(
        "SELECT wallet FROM positions WHERE position_id = 'Own1'"
    ).fetchone()
    assert row["wallet"] == WALLET_A
