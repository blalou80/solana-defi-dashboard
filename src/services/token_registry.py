"""Token metadata registry (W2).

Resolves mint -> {symbol, name, decimals} for ANY SPL mint without a
hardcoded list, using two real on-chain/API sources:

- **Metaplex metadata PDA** (via RPC ``getAccountInfo``): authoritative
  name/symbol/uri written by the mint's creator. Layout parsed per the
  Metaplex Metadata V1 account format.
- **Jupiter Price API v3**: decimals (and the price itself) for tradable
  mints.

Results are cached in the ``token_meta`` SQLite table (TTL 30 days). A
mint whose metadata cannot be resolved is stored with NULL symbol/name —
the UI then falls back to a mint-prefix label; a name is never guessed.
"""

import base64
import logging
import struct
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from solders.pubkey import Pubkey

from ..db import get_token_meta, upsert_token_meta
from ..utils import async_retry
from .market_data import _rpc_call

logger = logging.getLogger(__name__)

METADATA_PROGRAM = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
CACHE_TTL_DAYS = 30

SOL_MINT = "So11111111111111111111111111111111111111112"
# Native SOL has no Metaplex account; it is a documented constant, not a guess.
_SEED = {
    SOL_MINT: {"symbol": "SOL", "name": "Solana", "decimals": 9,
               "source": "protocol-constant"},
}


def metaplex_pda(mint: str) -> str:
    """Find the Metaplex metadata account for a mint."""
    program = Pubkey.from_string(METADATA_PROGRAM)
    pda, _bump = Pubkey.find_program_address(
        [b"metadata", bytes(program), bytes(Pubkey.from_string(mint))], program
    )
    return str(pda)


def parse_metaplex_metadata(data: bytes) -> Optional[Dict[str, str]]:
    """Parse name/symbol/uri from a Metadata V1 account's raw bytes.

    Layout: key(1) update_authority(32) mint(32) then borsh strings:
    name u32+bytes, symbol u32+bytes, uri u32+bytes. Returns None for
    anything that does not parse — callers treat that as unavailable.
    """
    try:
        off = 1 + 32 + 32

        def _string(offset: int) -> tuple[str, int]:
            (length,) = struct.unpack_from("<I", data, offset)
            raw = data[offset + 4 : offset + 4 + length]
            return raw.decode("utf-8", errors="replace").strip("\x00"), offset + 4 + length

        name, off = _string(off)
        symbol, off = _string(off)
        uri, _ = _string(off)
        return {"name": name, "symbol": symbol, "uri": uri}
    except Exception:
        return None


def _cache_fresh(row: Dict) -> bool:
    try:
        fetched = datetime.fromisoformat(row["fetched_ts"])
    except (TypeError, ValueError):
        return False
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - fetched).days
    return age_days < CACHE_TTL_DAYS


@async_retry(max_attempts=2, delay=1.0, backoff=2.0)
async def _fetch_metadata(session, rpc_url: str, mint: str) -> Optional[Dict[str, str]]:
    result = await _rpc_call(
        session, rpc_url, "getAccountInfo",
        [metaplex_pda(mint), {"encoding": "base64"}],
    )
    value = result.get("value")
    if not value:
        return None
    raw = base64.b64decode(value["data"][0])
    return parse_metaplex_metadata(raw)


async def resolve_mints(
    conn,
    mints: Iterable[str],
    rpc_url: str,
    decimals_hint: Optional[Dict[str, int]] = None,
) -> Dict[str, Dict]:
    """Return {mint: {symbol, name, decimals}} for all mints, using the
    SQLite cache first and fetching only stale/unknown entries."""
    import aiohttp

    decimals_hint = decimals_hint or {}
    out: Dict[str, Dict] = {}
    to_fetch: List[str] = []
    for mint in mints:
        if mint in _SEED:
            out[mint] = dict(_SEED[mint])
            continue
        row = get_token_meta(conn, mint)
        if row and _cache_fresh(row) and (
            row.get("decimals") is not None or mint not in decimals_hint
        ):
            out[mint] = {
                "symbol": row["symbol"], "name": row["name"],
                "decimals": row["decimals"],
            }
        else:
            to_fetch.append(mint)

    if to_fetch:
        async with aiohttp.ClientSession() as session:
            for mint in to_fetch:
                meta: Dict[str, Optional[str]] = {
                    "symbol": None, "name": None,
                    "decimals": decimals_hint.get(mint),
                }
                try:
                    parsed = await _fetch_metadata(session, rpc_url, mint)
                    if parsed:
                        meta["symbol"] = parsed["symbol"] or None
                        meta["name"] = parsed["name"] or None
                except Exception as e:
                    logger.warning(f"metadata fetch failed for {mint[:8]}…: {e}")
                upsert_token_meta(
                    conn, mint, meta["symbol"], meta["name"],
                    meta["decimals"], None, source="metaplex+price-v3",
                )
                out[mint] = meta
    return out


def display_symbol(info: Optional[Dict], mint: str) -> str:
    """Best honest label for a mint: registry symbol, else mint prefix."""
    if info and info.get("symbol"):
        return info["symbol"]
    return f"{mint[:4]}…"
