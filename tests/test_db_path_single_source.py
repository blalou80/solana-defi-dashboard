"""S1 regression: a custom db_path must never split the store again.

Bug class (post-MIRROR audit): cli.py and trade.py opened
get_connection() (default path) while everything else honored
config.db_path — quotes landed in a database the UI would never read.
"""

import re
from pathlib import Path

from src.db import conn_for, list_quotes, record_quote

SRC = Path(__file__).resolve().parents[1] / "src"

QUOTE = {
    "inputMint": "So11111111111111111111111111111111111111112",
    "inAmount": "1",
    "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "outAmount": "42",
    "priceImpactPct": "0",
    "slippageBps": 50,
    "routePlan": [],
}


class _Cfg:
    def __init__(self, db_path):
        self.db_path = db_path


def test_conn_for_honors_custom_db_path(tmp_path):
    custom = str(tmp_path / "elsewhere" / "my.db")
    conn = conn_for(_Cfg(custom))
    assert Path(custom).exists()
    conn.close()


def test_conn_for_none_uses_default(tmp_path, monkeypatch):
    monkeypatch.setenv("DEFI_DB_PATH", str(tmp_path / "env.db"))
    conn = conn_for(None)
    assert (tmp_path / "env.db").exists()
    conn.close()


def test_quote_written_via_conn_for_is_visible_to_a_fresh_conn_for(tmp_path):
    """Two 'processes' (fresh connections), one custom path, one database."""
    custom = str(tmp_path / "shared.db")
    writer = conn_for(_Cfg(custom))
    record_quote(writer, QUOTE)
    writer.close()

    reader = conn_for(_Cfg(custom))
    rows = list_quotes(reader)
    reader.close()
    assert len(rows) == 1 and rows[0]["out_amount"] == "42"


def test_no_module_bypasses_conn_for():
    """Static guard: outside src/db.py, nobody may call get_connection()
    directly — the single entry point is conn_for(config)."""
    offenders = []
    for py in SRC.rglob("*.py"):
        if py.name == "db.py":
            continue
        text = py.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            if re.search(r"\bget_connection\s*\(", line) and "import" not in line:
                offenders.append(f"{py.relative_to(SRC)}:{i}")
    assert not offenders, f"direct get_connection calls: {offenders}"
