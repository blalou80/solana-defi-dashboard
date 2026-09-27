"""W3 tests: position history queries, 7-day prune, and the IL
since-first-observation proxy (entry price is a labeled proxy, never a
claimed on-chain entry)."""

from datetime import datetime, timedelta, timezone

import pytest

from src.db import (
    get_connection,
    position_history,
    prune_position_history,
    record_positions,
)
from src.models import CLPosition
from src.risk.metrics import position_impermanent_loss

PID = "TestPosition1111111111111111111111111111111"


@pytest.fixture
def conn(tmp_path):
    c = get_connection(str(tmp_path / "h.db"))
    yield c
    c.close()


def _pos(tick=0, lower=-100, upper=100, fees_a=0.0, in_range=True):
    return CLPosition(
        position_id=PID, dex_name="Orca", pool_address="pool",
        token_a="SOL", token_b="USDC", tick_lower=lower, tick_upper=upper,
        current_tick=tick, liquidity=1.0, fees_owed_a=fees_a,
        is_in_range=in_range,
    )


def _ts(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def test_history_is_chronological(conn):
    # record_positions stamps NOW; insert with explicit ts via SQL for order test
    for t in (-3, -1, -2):
        conn.execute(
            """INSERT INTO positions (ts, position_id, dex_name, pool_address,
               token_a, token_b, tick_lower, tick_upper, current_tick,
               liquidity, fees_owed_a, fees_owed_b, impermanent_loss,
               is_in_range, source)
               VALUES (?, ?, 'Orca', 'p', 'SOL', 'USDC', -100, 100, ?, 1, 0, 0, 0, 1, 't')""",
            (_ts(abs(t) * -1 if False else abs(t)), PID, t),
        )
    conn.commit()
    hist = position_history(conn, PID)
    ticks = [h["current_tick"] for h in hist]
    assert ticks == sorted(ticks)  # oldest (-3d) to newest (-1d)


def test_prune_removes_only_old_rows(conn):
    rows = [(_ts(9), "old"), (_ts(1), "recent"), (_ts(0), "now")]
    for ts, _ in rows:
        conn.execute(
            """INSERT INTO positions (ts, position_id, dex_name, pool_address,
               token_a, token_b, tick_lower, tick_upper, current_tick,
               liquidity, fees_owed_a, fees_owed_b, impermanent_loss,
               is_in_range, source)
               VALUES (?, ?, 'Orca', 'p', 'SOL', 'USDC', -100, 100, 0, 1, 0, 0, 0, 1, 't')""",
            (ts, PID),
        )
    conn.commit()
    assert prune_position_history(conn, days=7) == 1
    assert len(position_history(conn, PID)) == 2


def test_record_positions_batches_are_one_history_row(conn):
    """One tick = one timestamp: duplicates within the batch are ignored,
    while a later tick (new timestamp) appends a new history row."""
    assert record_positions(conn, [_pos(), _pos()], source="t") == 1
    assert len(position_history(conn, PID)) == 1
    assert record_positions(conn, [_pos(tick=5)], source="t") == 1
    assert [h["current_tick"] for h in position_history(conn, PID)] == [0, 5]


# --- IL proxy -------------------------------------------------------------

def test_il_none_with_insufficient_history():
    assert position_impermanent_loss([]) is None
    assert position_impermanent_loss([{"current_tick": 0}]) is None


def test_il_zero_when_price_flat():
    hist = [{"current_tick": -1000}, {"current_tick": -1000}]
    assert position_impermanent_loss(hist) == pytest.approx(0.0)


def test_il_matches_closed_form_on_2x_price():
    # tick for 2x price: ln(2)/ln(1.0001)
    import math

    t2 = int(math.log(2) / math.log(1.0001))
    il = position_impermanent_loss([{"current_tick": 0}, {"current_tick": t2}])
    expected = (1 - 2 * math.sqrt(2) / 3) * 100  # classic 2x IL ≈ 5.72%
    assert il == pytest.approx(expected, rel=1e-3)


def test_il_uses_first_and_last_rows_only():
    hist = [{"current_tick": 0}, {"current_tick": 99999}, {"current_tick": 0}]
    # first vs last are equal -> zero despite the wild middle row
    assert position_impermanent_loss(hist) == pytest.approx(0.0)
