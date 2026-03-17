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


def test_community_block_tables_exist() -> None:
    conn = sqlite3.connect(":memory:")
    apply_all_sqlite_migrations(conn)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    assert "community_runtime_config" in tables
    assert "community_chats" in tables
    assert "community_content_items" in tables
    assert "community_post_log" in tables
    assert "community_thread_events" in tables


def test_community_block_expected_columns_exist() -> None:
    conn = sqlite3.connect(":memory:")
    apply_all_sqlite_migrations(conn)

    assert {
        "chat_id",
        "chat_key",
        "chat_type",
        "region",
        "has_topics",
        "default_topic_id",
        "is_enabled",
        "daily_post_time",
        "max_posts_per_day",
        "cooldown_hours",
        "last_posted_at",
    }.issubset(table_columns(conn, "community_chats"))

    assert {
        "id",
        "text",
        "format_type",
        "topic",
        "region",
        "has_question",
        "difficulty",
        "is_active",
        "priority",
    }.issubset(table_columns(conn, "community_content_items"))

    assert {
        "id",
        "chat_id",
        "content_id",
        "thread_root_message_id",
        "posted_message_id",
        "posted_at",
        "had_replies",
        "replies_count",
        "unique_users_count",
        "reply_latency_first_sec",
        "thread_depth_max",
        "followup_sent",
        "followup_posted_at",
        "thread_reactivated_after_followup",
    }.issubset(table_columns(conn, "community_post_log"))

    assert {
        "id",
        "chat_id",
        "post_log_id",
        "thread_root_message_id",
        "message_id",
        "user_id",
        "event_type",
        "created_at",
    }.issubset(table_columns(conn, "community_thread_events"))


def test_community_runtime_defaults_exist() -> None:
    conn = sqlite3.connect(":memory:")
    apply_all_sqlite_migrations(conn)

    rows = dict(
        conn.execute(
            "SELECT key, value_text FROM community_runtime_config"
        ).fetchall()
    )

    assert rows["global_enabled"] == "1"
    assert rows["followups_enabled"] == "0"
    assert rows["default_mode"] == "A"
