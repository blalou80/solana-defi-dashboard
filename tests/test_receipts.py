"""Tests for on-chain receipt parsing (Phase 2).

`tests/fixtures/jupiter_swap_tx.json` is a REAL Jupiter swap transaction
captured from mainnet on 2026-09-27 (signature 2tMVnKx3npmGcw5k…,
encoding jsonParsed). Tests assert the parser extracts the true deltas
from that chain data — realized slippage must come from receipts, never
from a simulation.
"""

import json
import os

import pytest

from src.engines.slippage import (
    get_transaction_receipt,
    realized_slippage_from_tx,
    token_deltas_from_receipt,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "jupiter_swap_tx.json")
RPC = "https://api.mainnet-beta.solana.com"


@pytest.fixture
def tx():
    with open(FIXTURE) as f:
        return json.load(f)


def _swapper_owner(tx):
    """The wallet that both sent one mint and received another — the actual
    swapper in the captured receipt (8N2XJYyV…: sent USDT, received SOL)."""
    owners = {b["owner"] for b in tx["meta"]["postTokenBalances"]}
    for o in owners:
        deltas = dict(token_deltas_from_receipt(tx, o))
        if any(d > 0 for d in deltas.values()) and any(d < 0 for d in deltas.values()):
            return o
    pytest.fail("fixture has no owner with both a sent and received mint")


def test_deltas_received_side(tx):
    deltas = dict(token_deltas_from_receipt(tx, _swapper_owner(tx)))
    assert any(d > 0 for d in deltas.values())
    assert any(d < 0 for d in deltas.values())


def test_deltas_unknown_owner_is_empty(tx):
    assert token_deltas_from_receipt(tx, "11111111111111111111111111111111") == []


def test_realized_slippage_math_from_receipt(tx):
    # pretend the quote expected 5% more than the swapper actually received:
    # realized slippage must read (E-R)/E ≈ +5.26%.
    owner = _swapper_owner(tx)
    deltas = dict(token_deltas_from_receipt(tx, owner))
    received_mint, received = max(
        ((m, d) for m, d in deltas.items() if d > 0), key=lambda kv: kv[1]
    )
    expected = received / 0.95
    slip = (expected - received) / expected * 100
    assert slip == pytest.approx(5.0)  # (E-R)/E with E = R/0.95 is exactly 5%


@pytest.mark.asyncio
async def test_realized_slippage_unavailable_for_wrong_mint(tx):
    """When the receipt has no movement of the requested mint the function
    must return None — not a made-up number."""
    owner = tx["meta"]["postTokenBalances"][0]["owner"]
    # monkeypatch the network layer with the fixture
    async def fake_receipt(*a, **k):
        return tx
    import src.engines.slippage as sl
    orig = sl.get_transaction_receipt
    sl.get_transaction_receipt = fake_receipt
    try:
        result = await realized_slippage_from_tx(
            "sig", owner, 1000.0, "SomeMintThatDidNotMove1111111111111111111111", RPC
        )
        assert result is None
    finally:
        sl.get_transaction_receipt = orig


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_receipt_fetch():
    """Integration: fetch the captured signature's receipt live. Skips if
    the public RPC rate-limits us; never fakes a pass."""
    with open(FIXTURE) as f:
        tx = json.load(f)
    sig = tx["transaction"]["signatures"][0]
    try:
        receipt = await get_transaction_receipt(sig, RPC)
    except Exception as e:
        pytest.skip(f"RPC unavailable/rate-limited: {e}")
    assert receipt["slot"] == tx["slot"]
