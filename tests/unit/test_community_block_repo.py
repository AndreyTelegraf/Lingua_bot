from __future__ import annotations

import sqlite3
from pathlib import Path

from services.community_block import repo


def apply_all_sqlite_migrations(conn: sqlite3.Connection) -> None:
    migrations_dir = Path("db/migrations_sqlite")
    for path in sorted(migrations_dir.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))


def build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_all_sqlite_migrations(conn)
    return conn


def test_runtime_flag_roundtrip() -> None:
    conn = build_conn()

    assert repo.get_runtime_flag(conn, key="global_enabled") == "1"
    repo.set_runtime_flag(conn, key="global_enabled", value="0")
    assert repo.get_runtime_flag(conn, key="global_enabled") == "0"


def test_chat_content_post_and_event_roundtrip() -> None:
    conn = build_conn()

    repo.upsert_chat(
        conn,
        chat_id=-100123456,
        chat_key="chatlisboa",
        chat_type="local",
        region="lisboa",
        has_topics=True,
        default_topic_id=777,
        is_enabled=True,
        daily_post_time="11:00",
        max_posts_per_day=1,
        cooldown_hours=24,
    )

    chat = repo.get_chat(conn, chat_id=-100123456)
    assert chat is not None
    assert chat["chat_key"] == "chatlisboa"
    assert chat["has_topics"] == 1
    assert chat["default_topic_id"] == 777

    content_id = repo.create_content_item(
        conn,
        text="Como é que vocês diriam isto em português de Portugal?",
        format_type="nuance",
        topic="idioms",
        region="lisboa",
        has_question=True,
        difficulty="light",
        is_active=True,
        priority=10,
    )

    post_log_id = repo.log_post(
        conn,
        chat_id=-100123456,
        content_id=content_id,
        thread_root_message_id=5001,
        posted_message_id=5001,
    )

    repo.record_thread_event(
        conn,
        chat_id=-100123456,
        post_log_id=post_log_id,
        thread_root_message_id=5001,
        message_id=5002,
        user_id=42,
        event_type="user_reply",
    )

    repo.update_post_reply_stats(
        conn,
        post_log_id=post_log_id,
        replies_count=3,
        unique_users_count=2,
        thread_depth_max=3,
        reply_latency_first_sec=240,
    )
    repo.mark_followup_sent(conn, post_log_id=post_log_id)
    repo.mark_thread_reactivated_after_followup(conn, post_log_id=post_log_id)

    row = conn.execute(
        """
        SELECT had_replies, replies_count, unique_users_count,
               thread_depth_max, reply_latency_first_sec,
               followup_sent, thread_reactivated_after_followup
        FROM community_post_log
        WHERE id = ?
        """,
        (post_log_id,),
    ).fetchone()

    assert row is not None
    assert row["had_replies"] == 1
    assert row["replies_count"] == 3
    assert row["unique_users_count"] == 2
    assert row["thread_depth_max"] == 3
    assert row["reply_latency_first_sec"] == 240
    assert row["followup_sent"] == 1
    assert row["thread_reactivated_after_followup"] == 1

    event_count = conn.execute(
        "SELECT COUNT(*) FROM community_thread_events WHERE post_log_id = ?",
        (post_log_id,),
    ).fetchone()[0]
    assert event_count == 1


def test_anti_repeat_window_check() -> None:
    conn = build_conn()

    repo.upsert_chat(
        conn,
        chat_id=-100999,
        chat_key="chatporto",
        chat_type="local",
        region="porto",
    )
    content_id = repo.create_content_item(
        conn,
        text="Test content",
        format_type="set",
    )

    assert repo.was_content_used_in_chat_within_days(
        conn,
        chat_id=-100999,
        content_id=content_id,
        days=90,
    ) is False

    repo.log_post(
        conn,
        chat_id=-100999,
        content_id=content_id,
        thread_root_message_id=9001,
        posted_message_id=9001,
    )

    assert repo.was_content_used_in_chat_within_days(
        conn,
        chat_id=-100999,
        content_id=content_id,
        days=90,
    ) is True
