from __future__ import annotations

import sqlite3
from pathlib import Path

from services.community_block import repo
from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block.decision import choose_post_candidate


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


def test_choose_candidate_after_binding_and_enable_only() -> None:
    conn = build_conn()

    repo.bind_chat_identity(
        conn,
        chat_key="chatlisboa",
        real_chat_id=-1001234567890,
        has_topics=True,
        default_topic_id=555,
    )
    repo.enable_only_chat(conn, chat_key="chatlisboa")
    conn.commit()

    chat = repo.get_chat_by_key(conn, chat_key="chatlisboa")
    assert chat is not None
    assert chat["is_enabled"] == 1
    assert chat["chat_id"] == -1001234567890
    assert chat["default_topic_id"] == 555

    decision = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=False)
    assert decision.allowed is True
    assert decision.content_id is not None


def test_log_post_roundtrip_for_manual_post() -> None:
    conn = build_conn()

    repo.bind_chat_identity(
        conn,
        chat_key="chatlisboa",
        real_chat_id=-1001234567890,
    )
    repo.enable_only_chat(conn, chat_key="chatlisboa")
    conn.commit()

    chat = repo.get_chat_by_key(conn, chat_key="chatlisboa")
    assert chat is not None

    decision = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=False)
    assert decision.allowed is True
    assert decision.content_id is not None

    post_log_id = repo.log_post(
        conn,
        chat_id=int(chat["chat_id"]),
        content_id=int(decision.content_id),
        thread_root_message_id=9001,
        posted_message_id=9001,
    )
    conn.commit()

    row = conn.execute(
        "SELECT chat_id, content_id, posted_message_id FROM community_post_log WHERE id = ?",
        (post_log_id,),
    ).fetchone()
    assert row is not None
    assert row["chat_id"] == -1001234567890
    assert row["content_id"] == int(decision.content_id)
    assert row["posted_message_id"] == 9001
