from __future__ import annotations

import sqlite3

import structlog
from aiogram import F, Router
from aiogram.types import Message

from app.config import get_settings
from services.community_block.ingress import IncomingCommunityMessage, handle_incoming_message

log = structlog.get_logger(__name__)


def _conn() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def build_community_ai_router() -> Router:
    router = Router(name="community_ai_router")

    @router.message(F.reply_to_message)
    async def community_ai_ingress_handler(message: Message) -> None:
        if message.chat.type not in {"group", "supergroup"}:
            return
        if message.from_user is None or message.from_user.is_bot:
            return
        if message.reply_to_message is None:
            return

        text = str(message.text or message.caption or "").strip()
        if not text:
            return

        incoming = IncomingCommunityMessage(
            chat_id=int(message.chat.id),
            message_id=int(message.message_id),
            user_id=int(message.from_user.id),
            text=text,
            reply_to_message_id=int(message.reply_to_message.message_id),
            message_thread_id=int(message.message_thread_id) if message.message_thread_id is not None else None,
            from_bot=bool(message.from_user.is_bot),
        )

        conn = _conn()
        try:
            result = handle_incoming_message(conn, incoming=incoming)
            log.info(
                "community_ai_ingress_processed",
                status=result.get("status"),
                reason=result.get("reason"),
                chat_id=incoming.chat_id,
                message_id=incoming.message_id,
                post_log_id=result.get("post_log_id"),
                event_id=result.get("event_id"),
                planned=bool(result.get("planned")),
            )
        except Exception:
            log.exception(
                "community_ai_ingress_failed",
                chat_id=incoming.chat_id,
                message_id=incoming.message_id,
                reply_to_message_id=incoming.reply_to_message_id,
            )
        finally:
            conn.close()

    return router
