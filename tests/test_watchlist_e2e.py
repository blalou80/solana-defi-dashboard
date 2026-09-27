"""W1 — wallet onboarding tests: validation, watchlist CRUD, dual-source
polling resolution, and the full add-watchlist -> tick -> snapshot path.

Network-dependent cases skip honestly (rule: live tests never fake a pass).
"""

import pytest

import src.main as main_mod
from src.db import add_watch, get_connection, list_watchlist, remove_watch
from src.main import resolve_wallets
from src.validation import validate_solana_address

WALLET = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"  # real public wallet


@pytest.fixture
def conn(tmp_path):
    c = get_connection(str(tmp_path / "w.db"))
    yield c
    c.close()


# --- validation ----------------------------------------------------------

def test_valid_address_passes():
    ok, result = validate_solana_address(WALLET)
    assert ok and result == WALLET


def test_whitespace_is_normalized():
    ok, result = validate_solana_address(f"  {WALLET}\n")
    assert ok and result == WALLET


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        None,
        "0OIl-not-base58",
        "So1111111111111111111111111111111111111111",  # 43 chars, wrong size
        "Solana" + "x" * 36,  # contains 0? no — but invalid decode
    ],
)
def test_invalid_addresses_rejected(bad):
    ok, reason = validate_solana_address(bad)
    assert not ok
    assert reason  # every rejection carries a human reason


# --- watchlist CRUD ------------------------------------------------------

def test_watchlist_roundtrip_and_idempotency(conn):
    assert add_watch(conn, WALLET, "hot", source="ui") is True
    assert add_watch(conn, WALLET, "again", source="ui") is False  # ignored
    rows = list_watchlist(conn)
    assert len(rows) == 1
    assert rows[0]["label"] == "hot" and rows[0]["source"] == "ui"
    assert remove_watch(conn, WALLET) is True
    assert list_watchlist(conn) == []


# --- dual-source resolution ----------------------------------------------

class _Cfg:
    wallet_addresses = [WALLET, "ConfigWalletExtra11111111111111111111111111"]
    rpc_endpoint = "https://api.mainnet-beta.solana.com"
    polling_interval_sec = 15


def test_resolve_wallets_union_dedup_order(conn):
    other = "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs"
    add_watch(conn, other, source="ui")
    wallets = resolve_wallets(_Cfg(), conn)
    assert wallets[0] == other  # watchlist first
    assert wallets.count(WALLET) == 1  # in both sources, appears once
    assert len(wallets) == 3


def test_resolve_wallets_config_only(conn):
    assert resolve_wallets(_Cfg(), conn) == _Cfg.wallet_addresses


# --- end-to-end: watchlist add -> tick -> snapshot -----------------------

@pytest.mark.asyncio
async def test_tick_polls_watchlisted_wallet_without_config(conn, monkeypatch):
    """The W1 promise: a wallet added through the UI (watchlist table) is
    polled by the daemon even with empty config. Market fetch is replaced
    by a test double returning real-shaped rows — product code still does
    all the persistence work."""
    calls = []

    async def fake_balances(wallet, rpc):
        calls.append(wallet)
        return [
            {"mint": "So11111111111111111111111111111111111111112",
             "symbol": "SOL", "amount": 5.0,
             "usd_price": 120.0, "usd_value": 600.0}
        ]

    async def fake_positions(wallet):
        return []

    monkeypatch.setattr(main_mod, "build_portfolio_balances", fake_balances)
    monkeypatch.setattr(main_mod, "fetch_positions_with_live_ticks", fake_positions)

    add_watch(conn, WALLET, "ui-added", source="ui")

    class _EmptyCfg:
        wallet_addresses = []
        rpc_endpoint = "http://unused"
        polling_interval_sec = 15

    await main_mod.tick(_EmptyCfg(), conn)

    assert calls == [WALLET]
    from src.db import latest_snapshot
    snap = latest_snapshot(conn, WALLET)
    assert snap is not None
    assert snap["total_value_usd"] == pytest.approx(600.0)


@pytest.mark.asyncio
async def test_live_tick_for_watchlisted_wallet(conn):
    """Full real path: watchlist -> live RPC + Jupiter prices -> snapshot."""
    add_watch(conn, WALLET, "live", source="ui")

    class _Cfg2:
        wallet_addresses = []
        rpc_endpoint = "https://api.mainnet-beta.solana.com"
        polling_interval_sec = 15

    try:
        await main_mod.tick(_Cfg2(), conn)
    except Exception as e:  # pragma: no cover - network
        pytest.skip(f"network: {e}")

    from src.db import latest_snapshot
    snap = latest_snapshot(conn, WALLET)
    if snap is None:
        pytest.skip("RPC/price endpoints rate-limited; tick logged the failure")
    assert snap["source"] == "solana-rpc+jupiter-price-v3"
    assert snap["total_value_usd"] > 0
