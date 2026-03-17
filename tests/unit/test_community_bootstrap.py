from __future__ import annotations

import sqlite3
from pathlib import Path

from services.community_block.bootstrap import bootstrap_community_layer


def apply_all_sqlite_migrations(conn: sqlite3.Connection) -> None:
    migrations_dir = Path("db/migrations_sqlite")
    for path in sorted(migrations_dir.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))


def test_bootstrap_creates_default_rows() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_all_sqlite_migrations(conn)

    bootstrap_community_layer(conn)
    conn.commit()

    chats = conn.execute("SELECT chat_key, is_enabled FROM community_chats ORDER BY chat_key").fetchall()
    assert [row["chat_key"] for row in chats] == [
        "chatalgarve",
        "chatleiria",
        "chatlisboa",
        "chatporto",
        "left4portugal",
    ]
    assert all(row["is_enabled"] == 0 for row in chats)

    content_count = conn.execute("SELECT COUNT(*) FROM community_content_items").fetchone()[0]
    assert content_count >= 3

    flags = dict(conn.execute("SELECT key, value_text FROM community_runtime_config").fetchall())
    assert flags["global_enabled"] == "1"
    assert flags["followups_enabled"] == "0"
    assert flags["default_mode"] == "A"
