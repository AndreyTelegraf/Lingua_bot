from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block import repo
from services.community_block.ai_planner import plan_and_persist


@dataclass(slots=True)
class IncomingCommunityMessage:
    chat_id: int
    message_id: int
    user_id: int
    text: str
    reply_to_message_id: int | None = None
    message_thread_id: int | None = None
    from_bot: bool = False


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _clean_text(text: str | None) -> str:
    return str(text or "").strip()


def handle_incoming_message(conn: sqlite3.Connection, *, incoming: IncomingCommunityMessage) -> dict:
    bootstrap_community_layer(conn)

    if incoming.from_bot:
        return {"ok": True, "status": "ignored", "reason": "from_bot"}

    text = _clean_text(incoming.text)
    if not text:
        return {"ok": True, "status": "ignored", "reason": "empty_text"}

    chat = repo.get_chat(conn, chat_id=int(incoming.chat_id))
    if chat is None:
        return {"ok": True, "status": "ignored", "reason": "unknown_chat"}

    if incoming.reply_to_message_id is None:
        return {"ok": True, "status": "ignored", "reason": "not_a_reply"}

    post = repo.find_post_log_by_reply_target(
        conn,
        chat_id=int(incoming.chat_id),
        reply_to_message_id=int(incoming.reply_to_message_id),
    )
    if post is None:
        return {"ok": True, "status": "ignored", "reason": "reply_not_linked_to_community_thread"}

    if repo.has_thread_event_for_message(
        conn,
        chat_id=int(incoming.chat_id),
        message_id=int(incoming.message_id),
    ):
        return {
            "ok": True,
            "status": "ignored",
            "reason": "duplicate_message_event",
            "post_log_id": int(post["id"]),
        }

    event_id = repo.record_thread_event_rich(
        conn,
        chat_id=int(incoming.chat_id),
        post_log_id=int(post["id"]),
        thread_root_message_id=int(post["thread_root_message_id"]) if post["thread_root_message_id"] is not None else None,
        message_id=int(incoming.message_id),
        user_id=int(incoming.user_id),
        event_type="user_reply",
        message_thread_id=incoming.message_thread_id,
        reply_to_message_id=int(incoming.reply_to_message_id) if incoming.reply_to_message_id is not None else None,
        message_text=text,
    )

    stats = repo.recompute_post_reply_stats(conn, post_log_id=int(post["id"]))
    conn.commit()

    ai_replies_enabled = str(repo.get_runtime_flag(conn, key="ai_replies_enabled", default="0") or "0") == "1"
    planned = None
    if ai_replies_enabled:
        min_user_replies = _to_int(repo.get_runtime_flag(conn, key="ai_min_user_replies", default="1"), 1)
        max_plans_per_thread = _to_int(repo.get_runtime_flag(conn, key="ai_max_plans_per_thread", default="2"), 2)
        planned = plan_and_persist(
            conn,
            post_log_id=int(post["id"]),
            min_user_replies=min_user_replies,
            max_plans_per_thread=max_plans_per_thread,
        )

    return {
        "ok": True,
        "status": "captured",
        "reason": "user_reply_captured",
        "chat_id": int(incoming.chat_id),
        "post_log_id": int(post["id"]),
        "thread_root_message_id": int(post["thread_root_message_id"]) if post["thread_root_message_id"] is not None else None,
        "event_id": int(event_id),
        "stats": stats,
        "planned": planned,
    }
