from __future__ import annotations

from aiogram import Bot


async def send_post(
    bot: Bot,
    *,
    chat_id: int,
    text: str,
    default_topic_id: int | None = None,
) -> int:
    kwargs: dict[str, object] = {
        "chat_id": chat_id,
        "text": text,
    }
    if default_topic_id is not None:
        kwargs["message_thread_id"] = int(default_topic_id)

    message = await bot.send_message(**kwargs)
    return int(message.message_id)
