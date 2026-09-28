"""WAL + busy_timeout must make concurrent daemon-writer / UI-reader
access safe — no 'database is locked' surfaces."""

import threading

import pytest

from src.db import get_connection, latest_snapshot, record_snapshot


@pytest.fixture
def dbfile(tmp_path):
    return str(tmp_path / "concurrent.db")


def test_wal_mode_enabled(dbfile):
    conn = get_connection(dbfile)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    conn.close()
    assert mode.lower() == "wal"
    assert timeout == 5000


def test_writer_reader_interleave_without_lock_errors(dbfile):
    """One writer thread (daemon-shaped: snapshot commits), four reader
    threads (dashboard-shaped: latest_snapshot). Any sqlite 'locked'
    OperationalError fails the test."""
    errors = []
    stop = threading.Event()
    n_writes = 60

    def writer():
        conn = get_connection(dbfile)
        for i in range(n_writes):
            try:
                record_snapshot(
                    conn, "W1", [{"mint": "SOL", "symbol": "SOL",
                                  "amount": float(i), "usd_price": 1.0,
                                  "usd_value": float(i)}],
                    source="test",
                )
            except Exception as e:  # pragma: no cover - the failure we test
                errors.append(("write", e))
                return
        stop.set()
        conn.close()

    def reader():
        conn = get_connection(dbfile)
        while not stop.is_set():
            try:
                latest_snapshot(conn, "W1")
            except Exception as e:
                errors.append(("read", e))
                return
        conn.close()

    threads = [threading.Thread(target=writer)] + [
        threading.Thread(target=reader) for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors, errors
    conn = get_connection(dbfile)
    count = conn.execute(
        "SELECT COUNT(*) FROM portfolio_snapshots"
    ).fetchone()[0]
    conn.close()
    assert count == n_writes


def test_price_requests_are_chunked():
    """Live evidence: a whale wallet's hundreds of mints blew the price
    API URL (HTTP 414). get_usd_prices must split into <=25-mint requests."""
    import asyncio

    from src.services import market_data as md

    seen: list[int] = []

    async def fake_batch(session, batch):
        seen.append(len(batch))
        return dict.fromkeys(batch, 1.0)

    md._get_usd_prices_batch = fake_batch  # type: ignore
    asyncio.run(md.get_usd_prices([f"mint{i}" for i in range(60)]))
    assert seen == [25, 25, 10]
