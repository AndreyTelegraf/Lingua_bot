from __future__ import annotations

import sqlite3
from pathlib import Path


def apply_all_sqlite_migrations(conn: sqlite3.Connection) -> None:
    migrations_dir = Path("db/migrations_sqlite")
    for path in sorted(migrations_dir.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def test_community_thread_events_v2_columns_exist() -> None:
    conn = sqlite3.connect(":memory:")
    apply_all_sqlite_migrations(conn)

    cols = table_columns(conn, "community_thread_events")
    assert {"message_thread_id", "reply_to_message_id", "message_text"}.issubset(cols)

    indexes = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    }
    assert "idx_community_thread_events_thread_root_created" in indexes
    assert "uidx_community_thread_events_chat_message" in indexes
