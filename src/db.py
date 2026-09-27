"""SQLite persistence layer.

Replaces the old cross-process "shared state" design, which was a
per-process global singleton: the daemon wrote it, the Streamlit process
read its own (always empty) copy. Both processes now communicate through
this file-backed store.

Every row records where its numbers came from (``source``) so the UI can
show provenance instead of trusting in-memory values.
"""

import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".data", "dashboard.db"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,                -- ISO-8601 UTC
    wallet TEXT NOT NULL,
    total_value_usd REAL NOT NULL,
    source TEXT NOT NULL             -- e.g. "solana-rpc+jupiter-price-v3"
);
CREATE TABLE IF NOT EXISTS token_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES portfolio_snapshots(id),
    mint TEXT NOT NULL,
    symbol TEXT,
    amount REAL NOT NULL,
    usd_price REAL,                  -- NULL = price unavailable, never faked
    usd_value REAL                   -- NULL when usd_price is NULL
);
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    position_id TEXT NOT NULL,
    dex_name TEXT NOT NULL,
    pool_address TEXT,
    token_a TEXT,
    token_b TEXT,
    tick_lower INTEGER,
    tick_upper INTEGER,
    current_tick INTEGER,
    liquidity REAL,
    fees_owed_a REAL,
    fees_owed_b REAL,
    impermanent_loss REAL,
    is_in_range INTEGER,
    source TEXT NOT NULL,
    wallet TEXT,                         -- S4: owner wallet (from the watchlist poll)
    UNIQUE (ts, position_id)
);
CREATE TABLE IF NOT EXISTS alerts_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    channel TEXT,
    target TEXT,                         -- what the alert was about (wallet/symbol/position)
    delivered INTEGER NOT NULL DEFAULT 0  -- 1 only after webhook 2xx
);
CREATE TABLE IF NOT EXISTS watchlist (
    wallet TEXT PRIMARY KEY,             -- validated base58 public key
    label TEXT,
    added_ts TEXT NOT NULL,
    source TEXT NOT NULL                 -- 'ui' | 'config'
);
CREATE TABLE IF NOT EXISTS token_meta (
    mint TEXT PRIMARY KEY,
    symbol TEXT,                         -- NULL = could not resolve (never guessed)
    name TEXT,
    decimals INTEGER,                    -- NULL = unknown; balances then render without price math
    logo_uri TEXT,
    fetched_ts TEXT NOT NULL,
    source TEXT NOT NULL                 -- 'metaplex+price-v3' etc.
);
CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,                  -- 'stop_loss' | 'boundary'
    symbol TEXT,                         -- mint symbol for stop_loss
    threshold REAL,
    channel TEXT NOT NULL,
    message_template TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    cooldown_min INTEGER NOT NULL DEFAULT 30,
    created_ts TEXT NOT NULL,
    source TEXT NOT NULL,                -- 'ui' | 'config'
    wallet TEXT                          -- S4: NULL = all watched wallets
);
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    input_mint TEXT NOT NULL,
    output_mint TEXT NOT NULL,
    in_amount TEXT,                      -- raw smallest-unit strings from Jupiter
    out_amount TEXT,
    price_impact_pct REAL,
    slippage_bps INTEGER,
    route_labels TEXT,                   -- JSON array of AMM labels in the plan
    source TEXT NOT NULL,                -- 'jupiter-swap-v1'
    wallet TEXT                          -- S4: who the quote was for (NULL = anonymous)
);
CREATE TABLE IF NOT EXISTS daily_values (
    wallet TEXT NOT NULL,
    date TEXT NOT NULL,                  -- YYYY-MM-DD (UTC)
    total_value_usd REAL NOT NULL,       -- last known value for that day
    updated_ts TEXT NOT NULL,
    PRIMARY KEY (wallet, date)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_wallet_ts ON portfolio_snapshots (wallet, ts);
CREATE INDEX IF NOT EXISTS idx_balances_snapshot ON token_balances (snapshot_id);
"""


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or os.getenv("DEFI_DB_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # S2: the daemon writes while Streamlit reads from another process.
    # WAL lets readers proceed during a writer's transaction, and the
    # busy timeout absorbs the remaining write-lock collisions instead of
    # surfacing "database is locked".
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")  # WAL-appropriate durability
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(_SCHEMA)
    # lightweight forward migration for pre-existing databases
    _MIGRATIONS = {
        "alerts_log": {"target": "TEXT"},
        "alert_rules": {"wallet": "TEXT"},
        "quotes": {"wallet": "TEXT"},
        "positions": {"wallet": "TEXT"},
    }
    for _table, _added in _MIGRATIONS.items():
        _cols = {r[1] for r in conn.execute(f"PRAGMA table_info({_table})")}
        for _col, _type in _added.items():
            if _col not in _cols:
                conn.execute(f"ALTER TABLE {_table} ADD COLUMN {_col} {_type}")
        conn.commit()
    return conn


def conn_for(config=None) -> sqlite3.Connection:
    """THE way to open the shared database (S1: single entry point).

    Every call site — daemon, CLI, dashboard pages — goes through here so
    a custom ``db_path`` in .config.yaml can never split the store into
    two databases again. ``config`` may be None (missing/invalid config
    file) and falls back to env/default path.
    """
    return get_connection(getattr(config, "db_path", None) if config else None)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_snapshot(
    conn: sqlite3.Connection,
    wallet: str,
    balances: List[Dict[str, Any]],
    source: str,
    ts: Optional[str] = None,
) -> int:
    """Insert one portfolio snapshot + its token balance rows.

    ``balances`` items: {mint, symbol, amount, usd_price (may be None)}.
    total_value_usd sums only rows with a real price; if no prices are
    available the total is 0.0 and the UI must show "unpriced", not a guess.
    """
    ts = ts or _utcnow()
    total = sum(
        b["usd_value"] for b in balances
        if b.get("usd_value") is not None
    )
    cur = conn.execute(
        "INSERT INTO portfolio_snapshots (ts, wallet, total_value_usd, source) "
        "VALUES (?, ?, ?, ?)",
        (ts, wallet, total, source),
    )
    snap_id = cur.lastrowid
    for b in balances:
        conn.execute(
            "INSERT INTO token_balances "
            "(snapshot_id, mint, symbol, amount, usd_price, usd_value) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                snap_id,
                b["mint"],
                b.get("symbol"),
                b["amount"],
                b.get("usd_price"),
                b.get("usd_value"),
            ),
        )
    # S3: same-day rollup so daily-resolution metrics are cheap and honest
    conn.execute(
        """INSERT INTO daily_values (wallet, date, total_value_usd, updated_ts)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(wallet, date) DO UPDATE SET
             total_value_usd=excluded.total_value_usd,
             updated_ts=excluded.updated_ts""",
        (wallet, ts[:10], total, ts),
    )
    conn.commit()
    return snap_id


def daily_value_history(conn: sqlite3.Connection, wallet: str) -> List[float]:
    """Chronological end-of-day portfolio values (oldest first)."""
    rows = conn.execute(
        "SELECT total_value_usd FROM daily_values WHERE wallet = ? "
        "ORDER BY date",
        (wallet,),
    ).fetchall()
    return [float(r["total_value_usd"]) for r in rows]


def latest_snapshot(conn: sqlite3.Connection, wallet: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM portfolio_snapshots WHERE wallet = ? "
        "ORDER BY ts DESC LIMIT 1",
        (wallet,),
    ).fetchone()
    if row is None:
        return None
    snap = dict(row)
    snap["balances"] = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM token_balances WHERE snapshot_id = ?", (snap["id"],)
        )
    ]
    return snap


def snapshot_value_history(
    conn: sqlite3.Connection, wallet: str, limit: int = 500
) -> List[float]:
    """Chronological total_value_usd series for one wallet (oldest first)."""
    rows = conn.execute(
        "SELECT total_value_usd FROM portfolio_snapshots WHERE wallet = ? "
        "ORDER BY ts DESC LIMIT ?",
        (wallet, limit),
    ).fetchall()
    return [float(r["total_value_usd"]) for r in reversed(rows)]


def log_alert(
    conn: sqlite3.Connection,
    type_: str,
    message: str,
    channel: Optional[str] = None,
    delivered: bool = False,
    target: Optional[str] = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO alerts_log (ts, type, message, channel, target, delivered) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (_utcnow(), type_, message, channel, target, 1 if delivered else 0),
    )
    conn.commit()
    return cur.lastrowid


def last_alert_ts(
    conn: sqlite3.Connection, type_: str, target: str
) -> Optional[str]:
    """Timestamp of the most recent logged alert for a (type, target) pair —
    used for cooldown so a condition fires once per window, not per tick."""
    row = conn.execute(
        "SELECT ts FROM alerts_log WHERE type = ? AND target = ? "
        "ORDER BY ts DESC LIMIT 1",
        (type_, target),
    ).fetchone()
    return row["ts"] if row else None


# --- watchlist ---------------------------------------------------------

def add_watch(
    conn: sqlite3.Connection, wallet: str, label: Optional[str] = None,
    source: str = "ui",
) -> bool:
    """Add a wallet to the watchlist. Returns True if newly added,
    False if already watched (idempotent)."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO watchlist (wallet, label, added_ts, source) "
        "VALUES (?, ?, ?, ?)",
        (wallet, label, _utcnow(), source),
    )
    conn.commit()
    return cur.rowcount == 1


def remove_watch(conn: sqlite3.Connection, wallet: str) -> bool:
    cur = conn.execute("DELETE FROM watchlist WHERE wallet = ?", (wallet,))
    conn.commit()
    return cur.rowcount == 1


def list_watchlist(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT wallet, label, added_ts, source FROM watchlist ORDER BY added_ts"
    ).fetchall()
    return [dict(r) for r in rows]


# --- token metadata cache -------------------------------------------------

def get_token_meta(conn: sqlite3.Connection, mint: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM token_meta WHERE mint = ?", (mint,)
    ).fetchone()
    return dict(row) if row else None


def find_mint_by_symbol(conn: sqlite3.Connection, symbol: str) -> Optional[str]:
    """Reverse lookup used by alert symbol resolution. If several cached
    mints share a symbol, none is silently chosen — the first by mint order
    is returned and the ambiguity is logged."""
    rows = conn.execute(
        "SELECT mint FROM token_meta WHERE symbol = ? COLLATE NOCASE ORDER BY mint",
        (symbol,),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        logging.getLogger(__name__).warning(
            f"symbol {symbol!r} is ambiguous across {len(rows)} cached mints; "
            f"using {rows[0]['mint'][:8]}…"
        )
    return rows[0]["mint"]


def upsert_token_meta(
    conn: sqlite3.Connection,
    mint: str,
    symbol: Optional[str],
    name: Optional[str],
    decimals: Optional[int],
    logo_uri: Optional[str],
    source: str,
) -> None:
    conn.execute(
        """INSERT INTO token_meta (mint, symbol, name, decimals, logo_uri, fetched_ts, source)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(mint) DO UPDATE SET
             symbol=COALESCE(excluded.symbol, token_meta.symbol),
             name=COALESCE(excluded.name, token_meta.name),
             decimals=COALESCE(excluded.decimals, token_meta.decimals),
             logo_uri=COALESCE(excluded.logo_uri, token_meta.logo_uri),
             fetched_ts=excluded.fetched_ts,
             source=excluded.source""",
        (mint, symbol, name, decimals, logo_uri, _utcnow(), source),
    )
    conn.commit()


def record_positions(
    conn: sqlite3.Connection, positions: List[Any], source: str,
    wallet: Optional[str] = None,
) -> int:
    """Upsert a batch of CLPosition-like rows for the current tick.

    Returns the number stored. Duplicate (ts, position_id) rows are
    ignored so re-running a tick is idempotent.
    """
    ts = _utcnow()
    stored = 0
    for p in positions:
        cur = conn.execute(
            """INSERT OR IGNORE INTO positions
               (ts, position_id, dex_name, pool_address, token_a, token_b,
                tick_lower, tick_upper, current_tick, liquidity,
                fees_owed_a, fees_owed_b, impermanent_loss, is_in_range, source, wallet)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ts, p.position_id, p.dex_name, p.pool_address, p.token_a, p.token_b,
                p.tick_lower, p.tick_upper, p.current_tick, p.liquidity,
                p.fees_owed_a, p.fees_owed_b, getattr(p, "impermanent_loss", 0.0),
                1 if p.is_in_range else 0, source, wallet,
            ),
        )
        stored += cur.rowcount
    conn.commit()
    return stored


def latest_positions(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Most recent snapshot of every position (by its own latest ts)."""
    rows = conn.execute(
        """SELECT p.* FROM positions p
           JOIN (SELECT position_id, MAX(ts) AS mts FROM positions GROUP BY position_id) l
             ON l.position_id = p.position_id AND l.mts = p.ts
           ORDER BY p.is_in_range ASC, p.ts DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def position_history(
    conn: sqlite3.Connection, position_id: str, limit: int = 2000
) -> List[Dict[str, Any]]:
    """Chronological (oldest first) rows for one position.

    The ``positions`` table is itself the history: the daemon appends a
    row every tick (UNIQUE(ts, position_id)), so no duplicate table is
    needed — W3.1 reuses that design deliberately.
    """
    rows = conn.execute(
        "SELECT * FROM positions WHERE position_id = ? "
        "ORDER BY ts ASC LIMIT ?",
        (position_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def prune_position_history(conn: sqlite3.Connection, days: int = 7) -> int:
    """Delete position rows older than ``days`` (bounds DB growth at
    15s cadence). Returns rows removed."""
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cur = conn.execute("DELETE FROM positions WHERE ts < ?", (cutoff,))
    conn.commit()
    return cur.rowcount


# --- alert rules (W4: durable, dashboard-managed) -------------------------

def add_alert_rule(
    conn: sqlite3.Connection,
    type_: str,
    channel: str,
    symbol: Optional[str] = None,
    threshold: Optional[float] = None,
    message_template: Optional[str] = None,
    enabled: bool = True,
    cooldown_min: int = 30,
    source: str = "ui",
    wallet: Optional[str] = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO alert_rules (type, symbol, threshold, channel,
             message_template, enabled, cooldown_min, created_ts, source, wallet)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            type_, symbol, threshold, channel, message_template,
            1 if enabled else 0, cooldown_min, _utcnow(), source, wallet,
        ),
    )
    conn.commit()
    return cur.lastrowid


def delete_alert_rule(conn: sqlite3.Connection, rule_id: int) -> bool:
    cur = conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
    conn.commit()
    return cur.rowcount == 1


def list_alert_rules(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM alert_rules ORDER BY created_ts"
    ).fetchall()
    return [dict(r) for r in rows]


# --- quote log (W4: every quote the product showed is auditable) ----------

def record_quote(
    conn: sqlite3.Connection,
    quote_data: Dict[str, Any],
    source: str = "jupiter-swap-v1",
    wallet: Optional[str] = None,
) -> int:
    """Persist the raw fields of a Jupiter swap/v1 quote response."""
    import json as _json

    labels = [
        (step.get("swapInfo") or {}).get("label", "unknown")
        for step in quote_data.get("routePlan") or []
    ]
    cur = conn.execute(
        """INSERT INTO quotes (ts, input_mint, output_mint, in_amount,
             out_amount, price_impact_pct, slippage_bps, route_labels, source, wallet)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            _utcnow(),
            quote_data.get("inputMint", ""),
            quote_data.get("outputMint", ""),
            str(quote_data.get("inAmount", "")),
            str(quote_data.get("outAmount", "")),
            float(quote_data.get("priceImpactPct", 0) or 0),
            int(quote_data.get("slippageBps", 0) or 0),
            _json.dumps(labels),
            source,
            wallet,
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_quotes(conn: sqlite3.Connection, limit: int = 50) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM quotes ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]
