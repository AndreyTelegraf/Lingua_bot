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


def get_chat_by_key(conn: sqlite3.Connection, *, chat_key: str) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT *
        FROM community_chats
        WHERE chat_key = ?
        """,
        (chat_key,),
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


def list_all_chats(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT *
        FROM community_chats
        ORDER BY chat_key
        """
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def disable_all_chats(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        """
        UPDATE community_chats
        SET is_enabled = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE is_enabled != 0
        """
    )
    return int(cur.rowcount)


def bind_chat_identity(
    conn: sqlite3.Connection,
    *,
    chat_key: str,
    real_chat_id: int,
    has_topics: bool = False,
    default_topic_id: int | None = None,
) -> None:
    conn.execute(
        """
        UPDATE community_chats
        SET chat_id = ?,
            has_topics = ?,
            default_topic_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE chat_key = ?
        """,
        (
            real_chat_id,
            1 if has_topics else 0,
            default_topic_id,
            chat_key,
        ),
    )


def enable_only_chat(conn: sqlite3.Connection, *, chat_key: str) -> None:
    conn.execute(
        """
        UPDATE community_chats
        SET is_enabled = CASE WHEN chat_key = ? THEN 1 ELSE 0 END,
            updated_at = CURRENT_TIMESTAMP
        """,
        (chat_key,),
    )


def set_chat_daily_post_time(conn: sqlite3.Connection, *, chat_key: str, daily_post_time: str) -> None:
    conn.execute(
        """
        UPDATE community_chats
        SET daily_post_time = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE chat_key = ?
        """,
        (daily_post_time, chat_key),
    )


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


def get_content_item(conn: sqlite3.Connection, *, content_id: int) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT *
        FROM community_content_items
        WHERE id = ?
        """,
        (content_id,),
    ).fetchone()
    return _row_to_dict(row)


def list_candidate_content(
    conn: sqlite3.Connection,
    *,
    region: str | None,
    excluded_format_type: str | None = None,
) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row

    params: list[object] = []
    where = ["is_active = 1"]

    if region is not None:
        where.append("(region IS NULL OR region = ?)")
        params.append(region)

    if excluded_format_type is not None:
        where.append("format_type != ?")
        params.append(excluded_format_type)

    sql = f"""
    SELECT *
    FROM community_content_items
    WHERE {" AND ".join(where)}
    ORDER BY priority ASC, id ASC
    """
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_last_post_for_chat(conn: sqlite3.Connection, *, chat_id: int) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT *
        FROM community_post_log
        WHERE chat_id = ?
        ORDER BY posted_at DESC, id DESC
        LIMIT 1
        """,
        (chat_id,),
    ).fetchone()
    return _row_to_dict(row)


def list_used_content_ids_for_chat(conn: sqlite3.Connection, *, chat_id: int) -> set[int]:
    rows = conn.execute(
        """
        SELECT DISTINCT content_id
        FROM community_post_log
        WHERE chat_id = ?
        """,
        (chat_id,),
    ).fetchall()
    return {int(row[0]) for row in rows}


def get_recent_format_types_for_chat(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    limit: int = 3,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT c.format_type
        FROM community_post_log p
        JOIN community_content_items c ON c.id = p.content_id
        WHERE p.chat_id = ?
        ORDER BY p.posted_at DESC, p.id DESC
        LIMIT ?
        """,
        (chat_id, limit),
    ).fetchall()
    return [str(row[0]) for row in rows]


def count_recent_format_type_usage(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    format_type: str,
    limit: int = 3,
) -> int:
    rows = get_recent_format_types_for_chat(conn, chat_id=chat_id, limit=limit)
    return sum(1 for item in rows if item == format_type)


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


def has_post_for_chat_on_date(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    yyyy_mm_dd: str,
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM community_post_log
        WHERE chat_id = ?
          AND date(posted_at) = ?
        LIMIT 1
        """,
        (chat_id, yyyy_mm_dd),
    ).fetchone()
    return row is not None

# community_ai_ingress_v2 helpers

def find_post_log_by_reply_target(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    reply_to_message_id: int,
) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        '''
        SELECT *
        FROM community_post_log
        WHERE chat_id = ?
          AND (
            thread_root_message_id = ?
            OR posted_message_id = ?
          )
        ORDER BY id DESC
        LIMIT 1
        ''',
        (chat_id, reply_to_message_id, reply_to_message_id),
    ).fetchone()
    if row is not None:
        return _row_to_dict(row)

    row = conn.execute(
        '''
        SELECT pl.*
        FROM community_thread_events ev
        JOIN community_post_log pl ON pl.id = ev.post_log_id
        WHERE ev.chat_id = ?
          AND ev.message_id = ?
        ORDER BY pl.id DESC
        LIMIT 1
        ''',
        (chat_id, reply_to_message_id),
    ).fetchone()
    return _row_to_dict(row)


def has_thread_event_for_message(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    message_id: int,
) -> bool:
    row = conn.execute(
        '''
        SELECT 1
        FROM community_thread_events
        WHERE chat_id = ? AND message_id = ?
        LIMIT 1
        ''',
        (chat_id, message_id),
    ).fetchone()
    return row is not None


def record_thread_event_rich(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    post_log_id: int | None,
    thread_root_message_id: int | None,
    message_id: int,
    user_id: int,
    event_type: str,
    message_thread_id: int | None = None,
    reply_to_message_id: int | None = None,
    message_text: str | None = None,
) -> int:
    cur = conn.execute(
        '''
        INSERT INTO community_thread_events(
            chat_id,
            post_log_id,
            thread_root_message_id,
            message_id,
            user_id,
            event_type,
            message_thread_id,
            reply_to_message_id,
            message_text
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            chat_id,
            post_log_id,
            thread_root_message_id,
            message_id,
            user_id,
            event_type,
            message_thread_id,
            reply_to_message_id,
            message_text,
        ),
    )
    return int(cur.lastrowid)


def recompute_post_reply_stats(conn: sqlite3.Connection, *, post_log_id: int) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    agg = conn.execute(
        '''
        SELECT
            COUNT(*) AS replies_count,
            COUNT(DISTINCT user_id) AS unique_users_count,
            MIN(created_at) AS first_reply_at
        FROM community_thread_events
        WHERE post_log_id = ?
          AND event_type = 'user_reply'
        ''',
        (post_log_id,),
    ).fetchone()

    post = conn.execute(
        '''
        SELECT posted_at
        FROM community_post_log
        WHERE id = ?
        ''',
        (post_log_id,),
    ).fetchone()

    replies_count = int(agg["replies_count"] or 0)
    unique_users_count = int(agg["unique_users_count"] or 0)
    thread_depth_max = 1 if replies_count > 0 else 0

    reply_latency_first_sec = None
    first_reply_at = agg["first_reply_at"]
    posted_at = post["posted_at"] if post is not None else None
    if first_reply_at and posted_at:
        from datetime import datetime
        first_dt = datetime.fromisoformat(str(first_reply_at).replace(" ", "T"))
        posted_dt = datetime.fromisoformat(str(posted_at).replace(" ", "T"))
        reply_latency_first_sec = max(0, int((first_dt - posted_dt).total_seconds()))

    conn.execute(
        '''
        UPDATE community_post_log
        SET had_replies = ?,
            replies_count = ?,
            unique_users_count = ?,
            thread_depth_max = ?,
            reply_latency_first_sec = ?
        WHERE id = ?
        ''',
        (
            1 if replies_count > 0 else 0,
            replies_count,
            unique_users_count,
            thread_depth_max,
            reply_latency_first_sec,
            post_log_id,
        ),
    )

    return {
        "replies_count": replies_count,
        "unique_users_count": unique_users_count,
        "thread_depth_max": thread_depth_max,
        "reply_latency_first_sec": reply_latency_first_sec,
    }

# community_ai_live_send_v4 helpers

def get_runtime_int(conn: sqlite3.Connection, *, key: str, default: int) -> int:
    raw = get_runtime_flag(conn, key=key, default=str(default))
    try:
        return int(str(raw))
    except Exception:
        return default


def get_ai_plan_log(conn: sqlite3.Connection, *, plan_log_id: int) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        '''
        SELECT *
        FROM community_ai_reply_plan_log
        WHERE id = ?
        ''',
        (plan_log_id,),
    ).fetchone()
    return _row_to_dict(row)


def has_ai_delivery_for_plan(conn: sqlite3.Connection, *, plan_log_id: int) -> bool:
    row = conn.execute(
        '''
        SELECT 1
        FROM community_ai_reply_delivery_log
        WHERE plan_log_id = ?
        LIMIT 1
        ''',
        (plan_log_id,),
    ).fetchone()
    return row is not None


def has_recent_ai_delivery_for_post(conn: sqlite3.Connection, *, post_log_id: int, cooldown_seconds: int) -> bool:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        '''
        SELECT created_at
        FROM community_ai_reply_delivery_log
        WHERE post_log_id = ?
          AND delivery_status IN ('sent_generated', 'sent_fallback')
        ORDER BY id DESC
        LIMIT 1
        ''',
        (post_log_id,),
    ).fetchone()
    if row is None:
        return False

    from datetime import datetime, UTC, timedelta
    created_at = datetime.fromisoformat(str(row["created_at"]).replace(" ", "T")).replace(tzinfo=UTC)
    now = datetime.now(UTC)
    return (now - created_at) < timedelta(seconds=max(0, cooldown_seconds))


def log_ai_reply_delivery(
    conn: sqlite3.Connection,
    *,
    chat_id: int,
    post_log_id: int | None,
    plan_log_id: int,
    trigger_message_id: int | None,
    reply_to_message_id: int | None,
    sent_message_id: int | None,
    delivery_status: str,
    provider: str | None = None,
    model: str | None = None,
    response_id: str | None = None,
    used_fallback: bool = False,
    delivered_text: str | None = None,
) -> int:
    cur = conn.execute(
        '''
        INSERT INTO community_ai_reply_delivery_log (
            chat_id,
            post_log_id,
            plan_log_id,
            trigger_message_id,
            reply_to_message_id,
            sent_message_id,
            delivery_status,
            provider,
            model,
            response_id,
            used_fallback,
            delivered_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            chat_id,
            post_log_id,
            plan_log_id,
            trigger_message_id,
            reply_to_message_id,
            sent_message_id,
            delivery_status,
            provider,
            model,
            response_id,
            1 if used_fallback else 0,
            delivered_text,
        ),
    )
    return int(cur.lastrowid)
