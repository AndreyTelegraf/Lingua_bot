from __future__ import annotations

import sqlite3
from pathlib import Path

from services.community_block import repo
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

    chats = conn.execute(
        "SELECT chat_key, chat_id, is_enabled FROM community_chats ORDER BY chat_key"
    ).fetchall()
    assert [(row["chat_key"], row["chat_id"]) for row in chats] == [
        ("chatalcochete", -1001975356498),
        ("chatalgarve", -1001690275466),
        ("chatfigueira", -1002102744104),
        ("chatleiria", -1001227461571),
        ("chatlisboa", -1001656765898),
        ("chatporto", -1001719116315),
        ("left4portugal", -1001620974633),
    ]
    assert all(row["is_enabled"] == 0 for row in chats)

    content_count = conn.execute("SELECT COUNT(*) FROM community_content_items").fetchone()[0]
    assert content_count >= 3

    flags = dict(conn.execute("SELECT key, value_text FROM community_runtime_config").fetchall())
    assert flags["global_enabled"] == "1"
    assert flags["followups_enabled"] == "0"
    assert flags["default_mode"] == "A"


def test_bootstrap_preserves_bound_chat_enabled_state_and_syncs_canonical_id() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_all_sqlite_migrations(conn)

    bootstrap_community_layer(conn)
    repo.bind_chat_identity(
        conn,
        chat_key="chatalgarve",
        real_chat_id=-999999,
        has_topics=False,
        default_topic_id=None,
    )
    repo.enable_only_chat(conn, chat_key="chatalgarve")
    conn.commit()

    bootstrap_community_layer(conn)
    conn.commit()

    row = repo.get_chat_by_key(conn, chat_key="chatalgarve")
    assert row is not None
    assert row["chat_id"] == -1001690275466
    assert row["is_enabled"] == 1
