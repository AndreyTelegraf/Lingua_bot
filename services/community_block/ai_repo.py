from __future__ import annotations

import json
import sqlite3

from .ai_policy import ThreadMessage, ThreadSnapshot, PlanDecision


def _row(conn: sqlite3.Connection, sql: str, params: tuple) -> sqlite3.Row | None:
    return conn.execute(sql, params).fetchone()


def fetch_latest_post_log_id_for_chat(conn: sqlite3.Connection, chat_key: str) -> int | None:
    row = _row(
        conn,
        """
        SELECT pl.id
        FROM community_post_log pl
        JOIN community_chats ch ON ch.chat_id = pl.chat_id
        WHERE ch.chat_key = ?
        ORDER BY pl.id DESC
        LIMIT 1
        """,
        (chat_key,),
    )
    return None if row is None else int(row["id"])


def fetch_thread_snapshot(conn: sqlite3.Connection, post_log_id: int) -> ThreadSnapshot:
    row = _row(
        conn,
        """
        SELECT
            pl.id AS post_log_id,
            pl.chat_id,
            pl.thread_root_message_id,
            pl.followup_sent,
            pl.replies_count,
            pl.unique_users_count,
            ch.chat_key,
            ch.chat_type,
            ch.region,
            ci.topic,
            ci.format_type,
            ci.text AS seed_text
        FROM community_post_log pl
        JOIN community_chats ch ON ch.chat_id = pl.chat_id
        JOIN community_content_items ci ON ci.id = pl.content_id
        WHERE pl.id = ?
        """,
        (post_log_id,),
    )
    if row is None:
        raise RuntimeError(f"unknown post_log_id: {post_log_id}")

    ai_plan_count_row = _row(
        conn,
        "SELECT COUNT(*) AS c FROM community_ai_reply_plan_log WHERE post_log_id = ?",
        (post_log_id,),
    )
    prior_ai_plan_count = 0 if ai_plan_count_row is None else int(ai_plan_count_row["c"])

    messages: list[ThreadMessage] = []
    messages.append(
        ThreadMessage(
            role="seed",
            text=str(row["seed_text"]),
            message_id=row["thread_root_message_id"],
            user_id=None,
            event_type="seed_post",
        )
    )

    event_rows = conn.execute(
        """
        SELECT message_id, user_id, event_type
        FROM community_thread_events
        WHERE post_log_id = ?
        ORDER BY id ASC
        """,
        (post_log_id,),
    ).fetchall()

    for ev in event_rows:
        event_type = str(ev["event_type"])
        role = "user"
        if event_type.startswith("ai_") or event_type.startswith("followup_"):
            role = "ai"
        text = f"[{event_type}]"
        messages.append(
            ThreadMessage(
                role=role,
                text=text,
                message_id=ev["message_id"],
                user_id=ev["user_id"],
                event_type=event_type,
            )
        )

    text_event_rows = conn.execute(
        """
        SELECT message_id, user_id, event_type
        FROM community_thread_events
        WHERE post_log_id = ? AND event_type IN ('user_reply_text', 'ai_reply_text')
        ORDER BY id ASC
        """,
        (post_log_id,),
    ).fetchall()

    for _ in text_event_rows:
        # reserved for future richer event storage
        pass

    return ThreadSnapshot(
        post_log_id=int(row["post_log_id"]),
        chat_id=int(row["chat_id"]),
        chat_key=str(row["chat_key"]),
        chat_type=str(row["chat_type"]),
        region=row["region"],
        thread_root_message_id=row["thread_root_message_id"],
        topic=row["topic"],
        format_type=row["format_type"],
        seed_text=str(row["seed_text"]),
        messages=messages,
        followup_sent=bool(row["followup_sent"]),
        replies_count=int(row["replies_count"]),
        unique_users_count=int(row["unique_users_count"]),
        prior_ai_plan_count=prior_ai_plan_count,
    )


def count_user_reply_events(snapshot: ThreadSnapshot) -> int:
    return sum(1 for m in snapshot.messages if m.role == "user")


def count_ai_reply_events(snapshot: ThreadSnapshot) -> int:
    return sum(1 for m in snapshot.messages if m.role == "ai")


def insert_reply_plan_log(
    conn: sqlite3.Connection,
    *,
    snapshot: ThreadSnapshot,
    decision: PlanDecision,
    prompt_payload: dict,
) -> int:
    trigger_message_id = None
    for msg in reversed(snapshot.messages):
        if msg.role == "user":
            trigger_message_id = msg.message_id
            break

    cur = conn.execute(
        """
        INSERT INTO community_ai_reply_plan_log (
            chat_id,
            post_log_id,
            thread_root_message_id,
            trigger_message_id,
            planner_version,
            plan_status,
            should_reply,
            reply_mode,
            confidence,
            risk_level,
            product_bridge_allowed,
            human_like_score,
            verbosity_score,
            canned_pattern_score,
            prompt_payload_json,
            candidates_json,
            selected_reply_text,
            reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot.chat_id,
            snapshot.post_log_id,
            snapshot.thread_root_message_id,
            trigger_message_id,
            "community_ai_planner_v1",
            "planned",
            1 if decision.should_reply else 0,
            decision.reply_mode,
            decision.confidence,
            decision.risk_level,
            1 if decision.product_bridge_allowed else 0,
            decision.human_like_score,
            decision.verbosity_score,
            decision.canned_pattern_score,
            json.dumps(prompt_payload, ensure_ascii=False, indent=2),
            json.dumps([c.as_dict() for c in decision.candidates], ensure_ascii=False, indent=2),
            decision.selected_reply_text,
            decision.reason,
        ),
    )
    return int(cur.lastrowid)
