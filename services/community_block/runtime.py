from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import structlog

from app.config import get_settings
from services.community_block import repo
from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block.decision import choose_post_candidate


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
            conn = None
            try:
                conn = _open_runtime_db()
                bootstrap_community_layer(conn)

                global_enabled = repo.get_runtime_flag(conn, key="global_enabled", default="1")
                followups_enabled = repo.get_runtime_flag(conn, key="followups_enabled", default="0")
                default_mode = repo.get_runtime_flag(conn, key="default_mode", default="A")
                all_chats = repo.list_all_chats(conn)

                log.info(
                    "community_runtime_tick",
                    dry_run=dry_run,
                    global_enabled=global_enabled,
                    followups_enabled=followups_enabled,
                    default_mode=default_mode,
                    chat_count=len(all_chats),
                )

                if global_enabled != "1":
                    log.info("community_runtime_globally_disabled")
                else:
                    for chat in all_chats:
                        decision = choose_post_candidate(
                            conn,
                            chat=chat,
                            recent_messages_count=0,
                            dry_run=dry_run,
                        )
                        log.info(
                            "community_decision",
                            dry_run=dry_run,
                            chat_id=chat["chat_id"],
                            chat_key=chat["chat_key"],
                            is_enabled=bool(chat["is_enabled"]),
                            reason=decision.reason,
                            allowed=decision.allowed,
                            content_id=decision.content_id,
                            content_format_type=decision.content_format_type,
                        )

                conn.commit()

            except Exception:
                log.exception("community_runtime_tick_failed")
            finally:
                if conn is not None:
                    conn.close()

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
