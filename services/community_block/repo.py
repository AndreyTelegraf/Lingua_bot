from __future__ import annotations

import sqlite3
from typing import Any


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def get_runtime_flag(conn: sqlite3.Connection, *, key: str, default: str | None = None) -> str | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT value_text
        FROM community_runtime_config
        WHERE key = ?
        """,
        (key,),
    ).fetchone()
    if row is None:
        return default
    return str(row["value_text"])


def set_runtime_flag(conn: sqlite3.Connection, *, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO community_runtime_config(key, value_text)
        VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value_text = excluded.value_text,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, value),
    )


def upsert_chat(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    chat_key: str,
    chat_type: str,
    region: str | None = None,
    has_topics: bool = False,
    default_topic_id: int | None = None,
    is_enabled: bool = True,
    daily_post_time: str = "11:00",
    max_posts_per_day: int = 1,
    cooldown_hours: int = 24,
) -> None:
    conn.execute(
        """
        INSERT INTO community_chats(
            chat_id,
            chat_key,
            chat_type,
            region,
            has_topics,
            default_topic_id,
            is_enabled,
            daily_post_time,
            max_posts_per_day,
            cooldown_hours
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            chat_key = excluded.chat_key,
            chat_type = excluded.chat_type,
            region = excluded.region,
            has_topics = excluded.has_topics,
            default_topic_id = excluded.default_topic_id,
            is_enabled = excluded.is_enabled,
            daily_post_time = excluded.daily_post_time,
            max_posts_per_day = excluded.max_posts_per_day,
            cooldown_hours = excluded.cooldown_hours,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            chat_id,
            chat_key,
            chat_type,
            region,
            1 if has_topics else 0,
            default_topic_id,
            1 if is_enabled else 0,
            daily_post_time,
            max_posts_per_day,
            cooldown_hours,
        ),
    )


def get_chat(conn: sqlite3.Connection, *, chat_id: int) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT *
        FROM community_chats
        WHERE chat_id = ?
        """,
        (chat_id,),
    ).fetchone()
    return _row_to_dict(row)


def list_enabled_chats(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT *
        FROM community_chats
        WHERE is_enabled = 1
        ORDER BY chat_key
        """
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def create_content_item(
    conn: sqlite3.Connection,
    *,
    text: str,
    format_type: str,
    topic: str | None = None,
    region: str | None = None,
    has_question: bool = False,
    difficulty: str = "light",
    is_active: bool = True,
    priority: int = 100,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO community_content_items(
            text,
            format_type,
            topic,
            region,
            has_question,
            difficulty,
            is_active,
            priority
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            text,
            format_type,
            topic,
            region,
            1 if has_question else 0,
            difficulty,
            1 if is_active else 0,
            priority,
        ),
    )
    return int(cur.lastrowid)


def log_post(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    content_id: int,
    thread_root_message_id: int | None = None,
    posted_message_id: int | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO community_post_log(
            chat_id,
            content_id,
            thread_root_message_id,
            posted_message_id
        )
        VALUES(?, ?, ?, ?)
        """,
        (chat_id, content_id, thread_root_message_id, posted_message_id),
    )
    conn.execute(
        """
        UPDATE community_chats
        SET last_posted_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE chat_id = ?
        """,
        (chat_id,),
    )
    return int(cur.lastrowid)


def record_thread_event(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    message_id: int,
    user_id: int,
    event_type: str,
    post_log_id: int | None = None,
    thread_root_message_id: int | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO community_thread_events(
            chat_id,
            post_log_id,
            thread_root_message_id,
            message_id,
            user_id,
            event_type
        )
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (chat_id, post_log_id, thread_root_message_id, message_id, user_id, event_type),
    )
    return int(cur.lastrowid)


def update_post_reply_stats(
    conn: sqlite3.Connection,
    *,
    post_log_id: int,
    replies_count: int,
    unique_users_count: int,
    thread_depth_max: int,
    reply_latency_first_sec: int | None = None,
) -> None:
    conn.execute(
        """
        UPDATE community_post_log
        SET had_replies = CASE WHEN ? > 0 THEN 1 ELSE 0 END,
            replies_count = ?,
            unique_users_count = ?,
            thread_depth_max = ?,
            reply_latency_first_sec = COALESCE(reply_latency_first_sec, ?)
        WHERE id = ?
        """,
        (
            replies_count,
            replies_count,
            unique_users_count,
            thread_depth_max,
            reply_latency_first_sec,
            post_log_id,
        ),
    )


def mark_followup_sent(conn: sqlite3.Connection, *, post_log_id: int) -> None:
    conn.execute(
        """
        UPDATE community_post_log
        SET followup_sent = 1,
            followup_posted_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (post_log_id,),
    )


def mark_thread_reactivated_after_followup(conn: sqlite3.Connection, *, post_log_id: int) -> None:
    conn.execute(
        """
        UPDATE community_post_log
        SET thread_reactivated_after_followup = 1
        WHERE id = ?
        """,
        (post_log_id,),
    )


def was_content_used_in_chat_within_days(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    content_id: int,
    days: int,
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM community_post_log
        WHERE chat_id = ?
          AND content_id = ?
          AND posted_at >= datetime('now', ?)
        LIMIT 1
        """,
        (chat_id, content_id, f"-{int(days)} days"),
    ).fetchone()
    return row is not None
