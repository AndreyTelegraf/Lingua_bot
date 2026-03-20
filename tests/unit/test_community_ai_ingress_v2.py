from __future__ import annotations

import sqlite3
from pathlib import Path

from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block import repo
from services.community_block.ingress import IncomingCommunityMessage, handle_incoming_message


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


def seed_post(conn: sqlite3.Connection) -> int:
    repo.bind_chat_identity(conn, chat_key="chatlisboa", real_chat_id=-1001656765898, has_topics=True, default_topic_id=1)
    repo.enable_only_chat(conn, chat_key="chatlisboa")
    content_id = repo.create_content_item(
        conn,
        text="Как бы вы сказали это по-простому, а не языком уставшего чиновника?",
        format_type="dialogue",
        topic="documents",
        region="lisboa",
        has_question=True,
        difficulty="light",
        is_active=True,
        priority=10,
    )
    post_log_id = repo.log_post(
        conn,
        chat_id=-1001656765898,
        content_id=content_id,
        thread_root_message_id=7001,
        posted_message_id=7001,
    )
    conn.commit()
    return post_log_id


def test_ingress_ignores_non_reply() -> None:
    conn = build_conn()
    seed_post(conn)

    result = handle_incoming_message(
        conn,
        incoming=IncomingCommunityMessage(
            chat_id=-1001656765898,
            message_id=8001,
            user_id=42,
            text="просто болтовня",
            reply_to_message_id=None,
        ),
    )
    assert result["status"] == "ignored"
    assert result["reason"] == "not_a_reply"


def test_ingress_captures_reply_and_updates_stats() -> None:
    conn = build_conn()
    post_log_id = seed_post(conn)

    result = handle_incoming_message(
        conn,
        incoming=IncomingCommunityMessage(
            chat_id=-1001656765898,
            message_id=8002,
            user_id=42,
            text="Я бы тут убрал официоз совсем",
            reply_to_message_id=7001,
            message_thread_id=1,
        ),
    )

    assert result["status"] == "captured"
    assert result["post_log_id"] == post_log_id
    assert result["stats"]["replies_count"] == 1
    assert result["stats"]["unique_users_count"] == 1

    ev = conn.execute(
        """
        SELECT event_type, message_thread_id, reply_to_message_id, message_text
        FROM community_thread_events
        WHERE post_log_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (post_log_id,),
    ).fetchone()
    assert ev is not None
    assert ev["event_type"] == "user_reply"
    assert ev["message_thread_id"] == 1
    assert ev["reply_to_message_id"] == 7001
    assert ev["message_text"] == "Я бы тут убрал официоз совсем"

    pl = conn.execute(
        """
        SELECT had_replies, replies_count, unique_users_count, thread_depth_max
        FROM community_post_log
        WHERE id = ?
        """,
        (post_log_id,),
    ).fetchone()
    assert pl is not None
    assert pl["had_replies"] == 1
    assert pl["replies_count"] == 1
    assert pl["unique_users_count"] == 1
    assert pl["thread_depth_max"] == 1


def test_ingress_autoplans_when_ai_enabled() -> None:
    conn = build_conn()
    post_log_id = seed_post(conn)
    repo.set_runtime_flag(conn, key="ai_replies_enabled", value="1")
    conn.commit()

    result = handle_incoming_message(
        conn,
        incoming=IncomingCommunityMessage(
            chat_id=-1001656765898,
            message_id=8003,
            user_id=42,
            text="А тут скорее как реально говорят?",
            reply_to_message_id=7001,
            message_thread_id=1,
        ),
    )

    assert result["status"] == "captured"
    assert result["planned"] is not None
    assert result["planned"]["decision"]["should_reply"] is True

    plan = conn.execute(
        """
        SELECT should_reply, selected_reply_text
        FROM community_ai_reply_plan_log
        WHERE post_log_id = ?
        ORDER BY id DESC LIMIT 1
        """,
        (post_log_id,),
    ).fetchone()
    assert plan is not None
    assert plan["should_reply"] == 1
    assert plan["selected_reply_text"]


def test_ingress_dedupes_same_message_id() -> None:
    conn = build_conn()
    post_log_id = seed_post(conn)

    payload = IncomingCommunityMessage(
        chat_id=-1001656765898,
        message_id=8004,
        user_id=42,
        text="Первый ответ",
        reply_to_message_id=7001,
        message_thread_id=1,
    )
    first = handle_incoming_message(conn, incoming=payload)
    second = handle_incoming_message(conn, incoming=payload)

    assert first["status"] == "captured"
    assert second["status"] == "ignored"
    assert second["reason"] == "duplicate_message_event"

    count = conn.execute(
        "SELECT COUNT(*) FROM community_thread_events WHERE post_log_id = ?",
        (post_log_id,),
    ).fetchone()[0]
    assert count == 1
