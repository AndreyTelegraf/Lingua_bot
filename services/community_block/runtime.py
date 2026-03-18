from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import structlog
from aiogram import Bot

from app.config import get_settings
from services.community_block import repo
from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block.clock import utc_now
from services.community_block.decision import choose_post_candidate
from services.community_block.schedule_gate import should_post_now
from services.community_block.sender import send_post


@dataclass(slots=True)
class CommunityRuntime:
    task: asyncio.Task | None = None
    stop_event: asyncio.Event | None = None


_runtime = CommunityRuntime()
log = structlog.get_logger(__name__)


def _open_runtime_db() -> sqlite3.Connection:
    settings = get_settings()
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path.as_posix())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


async def _maybe_send_scheduled_posts(*, dry_run_default: bool) -> None:
    settings = get_settings()
    now = utc_now()
    conn = _open_runtime_db()
    try:
        bootstrap_community_layer(conn)

        global_enabled = repo.get_runtime_flag(conn, key="global_enabled", default="1")
        followups_enabled = repo.get_runtime_flag(conn, key="followups_enabled", default="0")
        default_mode = repo.get_runtime_flag(conn, key="default_mode", default="A")
        dry_run_override = repo.get_runtime_flag(conn, key="dry_run_override", default=None)

        if dry_run_override is None:
            effective_dry_run = dry_run_default
        else:
            effective_dry_run = str(dry_run_override) == "1"

        all_chats = repo.list_all_chats(conn)

        log.info(
            "community_runtime_tick",
            dry_run=effective_dry_run,
            dry_run_override=dry_run_override,
            global_enabled=global_enabled,
            followups_enabled=followups_enabled,
            default_mode=default_mode,
            chat_count=len(all_chats),
        )

        if global_enabled != "1":
            log.info("community_runtime_globally_disabled")
            conn.commit()
            return

        bot: Bot | None = None
        try:
            for chat in all_chats:
                gate = should_post_now(
                    now=now,
                    daily_post_time=str(chat["daily_post_time"]),
                )

                if not gate.allowed:
                    log.info(
                        "community_schedule_gate",
                        chat_id=chat["chat_id"],
                        chat_key=chat["chat_key"],
                        reason=gate.reason,
                        daily_post_time=chat["daily_post_time"],
                        now=now.isoformat(),
                    )
                    continue

                if repo.has_post_for_chat_on_date(
                    conn,
                    chat_id=int(chat["chat_id"]),
                    yyyy_mm_dd=now.date().isoformat(),
                ):
                    log.info(
                        "community_schedule_gate",
                        chat_id=chat["chat_id"],
                        chat_key=chat["chat_key"],
                        reason="already_posted_today",
                        daily_post_time=chat["daily_post_time"],
                        now=now.isoformat(),
                    )
                    continue

                decision = choose_post_candidate(
                    conn,
                    chat=chat,
                    recent_messages_count=0,
                    dry_run=effective_dry_run,
                )
                log.info(
                    "community_decision",
                    dry_run=effective_dry_run,
                    chat_id=chat["chat_id"],
                    chat_key=chat["chat_key"],
                    is_enabled=bool(chat["is_enabled"]),
                    reason=decision.reason,
                    allowed=decision.allowed,
                    content_id=decision.content_id,
                    content_format_type=decision.content_format_type,
                )

                if not decision.allowed:
                    continue

                content = repo.get_content_item(conn, content_id=int(decision.content_id))
                if content is None:
                    log.info(
                        "community_send_skipped",
                        chat_id=chat["chat_id"],
                        chat_key=chat["chat_key"],
                        reason="missing_content",
                        content_id=decision.content_id,
                    )
                    continue

                if effective_dry_run:
                    log.info(
                        "community_send_planned",
                        dry_run=True,
                        chat_id=chat["chat_id"],
                        chat_key=chat["chat_key"],
                        content_id=content["id"],
                        daily_post_time=chat["daily_post_time"],
                    )
                    continue

                if bot is None:
                    bot = Bot(token=settings.bot_token)

                message_id = await send_post(
                    bot,
                    chat_id=int(chat["chat_id"]),
                    text=str(content["text"]),
                    default_topic_id=chat["default_topic_id"],
                )

                post_log_id = repo.log_post(
                    conn,
                    chat_id=int(chat["chat_id"]),
                    content_id=int(content["id"]),
                    thread_root_message_id=message_id,
                    posted_message_id=message_id,
                )
                conn.commit()

                log.info(
                    "community_post_sent",
                    dry_run=False,
                    chat_id=chat["chat_id"],
                    chat_key=chat["chat_key"],
                    content_id=content["id"],
                    posted_message_id=message_id,
                    post_log_id=post_log_id,
                )
        finally:
            if bot is not None:
                await bot.session.close()

        conn.commit()
    finally:
        conn.close()


async def _run_loop(*, tick_seconds: int, dry_run: bool) -> None:
    settings = get_settings()
    log.info(
        "community_runtime_started",
        app_env=settings.app_env,
        dry_run=dry_run,
        tick_seconds=tick_seconds,
    )

    try:
        while _runtime.stop_event is not None and not _runtime.stop_event.is_set():
            try:
                await _maybe_send_scheduled_posts(dry_run_default=dry_run)
            except Exception:
                log.exception("community_runtime_tick_failed")

            try:
                await asyncio.wait_for(_runtime.stop_event.wait(), timeout=tick_seconds)
            except asyncio.TimeoutError:
                continue
    except asyncio.CancelledError:
        log.info("community_runtime_cancelled")
        raise
    finally:
        log.info("community_runtime_stopped")


async def start_community_runtime() -> bool:
    settings = get_settings()
    if not settings.feature_community_enabled:
        log.info("community_runtime_disabled_by_feature_flag")
        return False

    if _runtime.task is not None and not _runtime.task.done():
        log.info("community_runtime_already_running")
        return True

    _runtime.stop_event = asyncio.Event()
    _runtime.task = asyncio.create_task(
        _run_loop(
            tick_seconds=max(5, int(settings.community_tick_seconds)),
            dry_run=bool(settings.community_dry_run),
        ),
        name="community_runtime",
    )
    return True


async def stop_community_runtime() -> None:
    if _runtime.task is None:
        return

    if _runtime.stop_event is not None:
        _runtime.stop_event.set()

    task = _runtime.task
    _runtime.task = None
    _runtime.stop_event = None

    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("community_runtime_stop_join_failed")
