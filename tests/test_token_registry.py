"""W2 token registry tests.

`tests/fixtures/metaplex_usdc.bin` is the REAL Metaplex metadata account
byte array for USDC, captured from mainnet RPC on 2026-09-27 — the parser
is tested against actual chain layout, not a hand-made guess.
"""

import os

import pytest

from src.db import find_mint_by_symbol, get_token_meta, upsert_token_meta
from src.services import token_registry as tr

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
JUP = "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "metaplex_usdc.bin")


@pytest.fixture
def conn(tmp_path):
    c = tr.__dict__  # noqa: F841 (document intent: module under test)
    from src.db import get_connection

    conn = get_connection(str(tmp_path / "reg.db"))
    yield conn
    conn.close()


# --- parser ---------------------------------------------------------------

def test_parse_real_usdc_metadata_bytes():
    with open(FIXTURE, "rb") as f:
        meta = tr.parse_metaplex_metadata(f.read())
    assert meta == {"name": "USD Coin", "symbol": "USDC", "uri": ""}


def test_parse_garbage_returns_none():
    assert tr.parse_metaplex_metadata(b"\x00\x01\x02") is None


def test_metaplex_pda_is_deterministic():
    # PDA derived live 2026-09-27 for the USDC mint
    assert tr.metaplex_pda(USDC) == "5x38Kp4hvdomTCnCrAny4UtMUt5rQBdB6px2K1Ui45Wq"


# --- cache behaviour --------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_uses_cache_on_second_call(conn, monkeypatch):
    calls = []

    async def fake_fetch(session, rpc, mint):
        calls.append(mint)
        return {"name": "Jupiter", "symbol": "JUP", "uri": ""}

    monkeypatch.setattr(tr, "_fetch_metadata", fake_fetch)
    a = await tr.resolve_mints(conn, [JUP], "http://rpc")
    b = await tr.resolve_mints(conn, [JUP], "http://rpc")
    assert a[JUP]["symbol"] == "JUP" and b[JUP]["symbol"] == "JUP"
    assert calls == [JUP]  # fetched once, then served from SQLite
    row = get_token_meta(conn, JUP)
    assert row["symbol"] == "JUP" and row["source"] == "metaplex+price-v3"


@pytest.mark.asyncio
async def test_unresolvable_mint_stays_none_not_guessed(conn, monkeypatch):
    async def fail(session, rpc, mint):
        raise RuntimeError("no metadata account")

    monkeypatch.setattr(tr, "_fetch_metadata", fail)
    out = await tr.resolve_mints(conn, ["SomeRandomMint111111111111111111111111"], "http://rpc")
    assert out[list(out)[0]]["symbol"] is None


@pytest.mark.asyncio
async def test_sol_is_protocol_seed(conn):
    out = await tr.resolve_mints(conn, [tr.SOL_MINT], "http://rpc")
    assert out[tr.SOL_MINT]["symbol"] == "SOL"
    assert out[tr.SOL_MINT]["decimals"] == 9


# --- symbol reverse lookup (alerts) ----------------------------------------

def test_find_mint_by_symbol_case_insensitive_and_ambiguous(conn, caplog):
    upsert_token_meta(conn, JUP, "JUP", "Jupiter", 6, None, source="test")
    upsert_token_meta(conn, "OtherMint111", "jup", "Fake", 6, None, source="test")
    assert find_mint_by_symbol(conn, "Jup").startswith("JUP")
    assert find_mint_by_symbol(conn, "nothing") is None
    assert "ambiguous" in caplog.text  # never silently picks


# --- balance scan aggregation (no per-mint allowlist) -----------------------

@pytest.mark.asyncio
async def test_wallet_scan_aggregates_all_programs(monkeypatch):
    from src.services import market_data as md

    async def fake_rpc(session, url, method, params):
        if method == "getBalance":
            return {"value": 1_500_000_000}
        if method == "getTokenAccountsByOwner":
            program = params[1]["programId"]
            if program.startswith("Tokenk"):
                return {"value": [
                    _acct(USDC, 2_000_000, 6), _acct(USDC, 500_000, 6),  # two accounts
                    _acct(JUP, 10_000_000_000, 6),
                ]}
            return {"value": [_acct("Token2022Mint1", 12345, 4)]}
        raise AssertionError(method)

    monkeypatch.setattr(md, "_rpc_call", fake_rpc)
    rows = await md.get_wallet_balances("W", "http://rpc")
    by = {r["mint"]: r for r in rows}
    assert by[tr.SOL_MINT]["amount"] == pytest.approx(1.5)
    assert by[USDC]["amount"] == pytest.approx(2.5)      # summed across accounts
    assert by[USDC]["decimals"] == 6
    assert "Token2022Mint1" in by                        # Token-2022 included
    assert "symbol" not in by[USDC]                      # symbol is registry's job


def _acct(mint, raw, decimals):
    return {"account": {"data": {"parsed": {"info": {
        "mint": mint,
        "tokenAmount": {"uiAmount": raw / 10**decimals, "decimals": decimals},
    }}}}}


# --- live integration -------------------------------------------------------

@pytest.mark.live
@pytest.mark.asyncio
async def test_live_resolve_usdc_and_jup(conn):
    try:
        out = await tr.resolve_mints(conn, [USDC, JUP], "https://api.mainnet-beta.solana.com")
    except Exception as e:
        pytest.skip(f"RPC unavailable: {e}")
    assert out[USDC]["symbol"] == "USDC"
    assert out[JUP]["symbol"] == "JUP"
