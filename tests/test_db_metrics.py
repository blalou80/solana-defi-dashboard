"""Tests for the SQLite persistence layer and history-driven metrics —
the Phase-0 replacement for the impossible cross-process global state."""

import pytest

from src.db import (
    get_connection,
    latest_snapshot,
    log_alert,
    record_snapshot,
)
from src.risk.metrics import compute_portfolio_metrics, returns_from_values

WALLET = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"


@pytest.fixture
def conn(tmp_path):
    c = get_connection(str(tmp_path / "test.db"))
    yield c
    c.close()


def test_snapshot_roundtrip(conn):
    balances = [
        {"mint": "SOLMINT", "symbol": "SOL", "amount": 10.0,
         "usd_price": 120.0, "usd_value": 1200.0},
        {"mint": "USDCMINT", "symbol": "USDC", "amount": 5.0,
         "usd_price": None, "usd_value": None},  # price unavailable
    ]
    sid = record_snapshot(conn, WALLET, balances, source="test")
    snap = latest_snapshot(conn, WALLET)
    assert snap["id"] == sid
    assert snap["total_value_usd"] == pytest.approx(1200.0)  # unpriced row excluded
    assert snap["source"] == "test"
    assert len(snap["balances"]) == 2


def test_latest_snapshot_none_for_unknown_wallet(conn):
    assert latest_snapshot(conn, "unknown") is None


def test_alert_log_records_delivery_flag(conn):
    log_alert(conn, "stop_loss", "SOL hit threshold", "telegram", delivered=True)
    log_alert(conn, "stop_loss_skipped", "no price", "telegram", delivered=False)
    rows = conn.execute("SELECT type, delivered FROM alerts_log ORDER BY id").fetchall()
    assert [(r["type"], r["delivered"]) for r in rows] == [
        ("stop_loss", 1), ("stop_loss_skipped", 0)
    ]


def test_returns_from_values():
    assert returns_from_values([]) == []
    assert returns_from_values([100.0]) == []
    r = returns_from_values([100.0, 110.0, 99.0])
    assert r[0] == pytest.approx(0.10)
    assert r[1] == pytest.approx(-0.10)


def test_metrics_empty_wallet_is_all_none(conn):
    p = compute_portfolio_metrics(conn, WALLET)
    assert p.total_value_usd == 0.0
    assert p.var_95 is None
    assert p.sharpe_ratio is None
    assert p.snapshot_count == 0


def test_metrics_refuses_low_history(conn):
    """With fewer than the minimum snapshots, VaR/Sharpe stay None —
    regression guard against the old seed-42 mock."""
    for i in range(4):  # < MIN_SAMPLES_SHARPE (5) and < MIN_SAMPLES_VAR (20)
        record_snapshot(
            conn, WALLET,
            [{"mint": "SOL", "symbol": "SOL", "amount": 1.0,
              "usd_price": 100.0 + i, "usd_value": 100.0 + i}],
            source="test",
        )
    p = compute_portfolio_metrics(conn, WALLET)
    assert p.total_value_usd == pytest.approx(103.0)
    assert p.var_95 is None
    assert p.sharpe_ratio is None
    assert p.snapshot_count == 4


def test_metrics_computed_from_real_history(conn):
    for i in range(25):
        record_snapshot(
            conn, WALLET,
            [{"mint": "SOL", "symbol": "SOL", "amount": 1.0,
              "usd_price": 100.0 + (i % 5), "usd_value": 100.0 + (i % 5)}],
            source="test",
        )
    p = compute_portfolio_metrics(conn, WALLET)
    assert p.var_95 is not None
    assert p.sharpe_ratio is not None
    assert p.snapshot_count == 25
