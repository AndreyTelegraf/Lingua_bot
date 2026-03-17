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


def test_choose_post_candidate_selects_first_available() -> None:
    conn = build_conn()
    chat = repo.get_chat_by_key(conn, chat_key="chatlisboa")
    assert chat is not None

    decision = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=True)

    assert decision.allowed is True
    assert decision.reason == "candidate_selected"
    assert decision.content_id is not None
    assert decision.content_format_type is not None


def test_choose_post_candidate_respects_activity_suppression() -> None:
    conn = build_conn()
    chat = repo.get_chat_by_key(conn, chat_key="chatlisboa")
    assert chat is not None

    decision = choose_post_candidate(conn, chat=chat, recent_messages_count=21, dry_run=True)

    assert decision.allowed is False
    assert decision.reason == "active_discussion"


def test_choose_post_candidate_respects_anti_repeat_90_days() -> None:
    conn = build_conn()
    chat = repo.get_chat_by_key(conn, chat_key="chatlisboa")
    assert chat is not None

    first = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=True)
    assert first.allowed is True
    assert first.content_id is not None

    repo.log_post(
        conn,
        chat_id=int(chat["chat_id"]),
        content_id=int(first.content_id),
        thread_root_message_id=1001,
        posted_message_id=1001,
    )
    conn.commit()

    second = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=True)
    assert not (second.allowed and second.content_id == first.content_id)


def test_choose_post_candidate_skips_same_format_as_last_post() -> None:
    conn = build_conn()
    chat = repo.get_chat_by_key(conn, chat_key="chatlisboa")
    assert chat is not None

    first = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=True)
    assert first.allowed is True
    assert first.content_id is not None
    assert first.content_format_type is not None

    repo.log_post(
        conn,
        chat_id=int(chat["chat_id"]),
        content_id=int(first.content_id),
        thread_root_message_id=1002,
        posted_message_id=1002,
    )
    conn.commit()

    second = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=True)
    if second.allowed:
        assert second.content_format_type != first.content_format_type
