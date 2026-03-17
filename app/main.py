import asyncio

import structlog
from aiogram import Bot, Dispatcher

from app.container import close_container, init_container
from app.logging import setup_logging
from bot.router import build_root_router
from services.community_block.runtime import (
    start_community_runtime,
    stop_community_runtime,
)


async def main() -> None:
    setup_logging()
    from app.config import get_settings

    settings = get_settings()
    log = structlog.get_logger(__name__)

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is empty")

    await init_container()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(build_root_router())

    log.info(
        "bot_starting",
        app_env=settings.app_env,
        db_path=settings.db_path,
    )

    try:
        await start_community_runtime()
        await dp.start_polling(bot)
    finally:
        await stop_community_runtime()
        await bot.session.close()
        await close_container()
        log.info("bot_stopped")


if __name__ == "__main__":
    asyncio.run(main())
