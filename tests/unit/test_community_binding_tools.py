from __future__ import annotations

import sqlite3
from pathlib import Path

from services.community_block import repo
from services.community_block.bootstrap import bootstrap_community_layer


def apply_all_sqlite_migrations(conn: sqlite3.Connection) -> None:
    migrations_dir = Path("db/migrations_sqlite")
    for path in sorted(migrations_dir.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))


def build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_all_sqlite_migrations(conn)
    bootstrap_community_layer(conn)
    conn.commit()
    return conn


def test_bind_chat_identity_updates_target_chat() -> None:
    conn = build_conn()

    repo.bind_chat_identity(
        conn,
        chat_key="chatlisboa",
        real_chat_id=-100777888,
        has_topics=True,
        default_topic_id=12345,
    )
    conn.commit()

    row = repo.get_chat_by_key(conn, chat_key="chatlisboa")
    assert row is not None
    assert row["chat_id"] == -100777888
    assert row["has_topics"] == 1
    assert row["default_topic_id"] == 12345


def test_enable_only_chat_disables_others() -> None:
    conn = build_conn()

    repo.enable_only_chat(conn, chat_key="chatporto")
    conn.commit()

    enabled = repo.list_enabled_chats(conn)
    assert [row["chat_key"] for row in enabled] == ["chatporto"]


def test_disable_all_chats_turns_everything_off() -> None:
    conn = build_conn()

    repo.enable_only_chat(conn, chat_key="chatporto")
    conn.commit()

    changed = repo.disable_all_chats(conn)
    conn.commit()

    assert changed >= 1
    assert repo.list_enabled_chats(conn) == []
