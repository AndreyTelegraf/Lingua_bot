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


def test_community_ai_reply_plan_log_schema_exists() -> None:
    conn = sqlite3.connect(":memory:")
    apply_all_sqlite_migrations(conn)

    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }

    assert "community_ai_reply_plan_log" in tables
    assert {
        "id",
        "chat_id",
        "post_log_id",
        "thread_root_message_id",
        "trigger_message_id",
        "planner_version",
        "plan_status",
        "should_reply",
        "reply_mode",
        "confidence",
        "risk_level",
        "product_bridge_allowed",
        "human_like_score",
        "verbosity_score",
        "canned_pattern_score",
        "prompt_payload_json",
        "candidates_json",
        "selected_reply_text",
        "reason",
        "created_at",
    }.issubset(table_columns(conn, "community_ai_reply_plan_log"))


def test_community_ai_runtime_defaults_exist() -> None:
    conn = sqlite3.connect(":memory:")
    apply_all_sqlite_migrations(conn)

    rows = dict(conn.execute("SELECT key, value_text FROM community_runtime_config").fetchall())

    assert rows["ai_replies_enabled"] == "0"
    assert rows["ai_provider"] == "openai"
    assert rows["ai_model"] == ""
    assert rows["ai_dry_run"] == "1"
    assert rows["ai_min_user_replies"] == "1"
    assert rows["ai_max_plans_per_thread"] == "2"
