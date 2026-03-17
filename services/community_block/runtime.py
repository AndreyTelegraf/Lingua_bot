from __future__ import annotations

import asyncio
from dataclasses import dataclass

import structlog

from app.config import get_settings
from db.connection import open_db
from services.community_block import repo


@dataclass(slots=True)
class CommunityRuntime:
    task: asyncio.Task | None = None
    stop_event: asyncio.Event | None = None


_runtime = CommunityRuntime()
log = structlog.get_logger(__name__)


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
            conn = await open_db()
            try:
                global_enabled = repo.get_runtime_flag(conn, key="global_enabled", default="1")
                followups_enabled = repo.get_runtime_flag(conn, key="followups_enabled", default="0")
                default_mode = repo.get_runtime_flag(conn, key="default_mode", default="A")
                enabled_chats = repo.list_enabled_chats(conn)
                log.info(
                    "community_runtime_tick",
                    dry_run=dry_run,
                    global_enabled=global_enabled,
                    followups_enabled=followups_enabled,
                    default_mode=default_mode,
                    enabled_chat_count=len(enabled_chats),
                )
            finally:
                await conn.close()

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
