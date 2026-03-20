from __future__ import annotations

import sqlite3
from pathlib import Path

from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block import repo
from services.community_block.ai_planner import plan_and_persist


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


def test_prompt_render_uses_real_user_text_and_no_seed_duplication() -> None:
    conn = build_conn()
    post_log_id = seed_post(conn)

    repo.record_thread_event_rich(
        conn,
        chat_id=-1001656765898,
        post_log_id=post_log_id,
        thread_root_message_id=7001,
        message_id=7002,
        user_id=42,
        event_type="user_reply",
        message_thread_id=1,
        reply_to_message_id=7001,
        message_text="А как это реально говорят в Lisboa?",
    )
    repo.recompute_post_reply_stats(conn, post_log_id=post_log_id)
    conn.commit()

    result = plan_and_persist(conn, post_log_id=post_log_id)
    prompt = result["prompt_payload"]["user_prompt"]

    assert prompt.count("seed: ") == 1
    assert "user: А как это реально говорят в Lisboa?" in prompt
    assert "[user_reply]" not in prompt
