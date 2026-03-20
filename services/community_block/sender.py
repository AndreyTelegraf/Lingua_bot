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

async def send_thread_reply(
    bot: Bot,
    *,
    chat_id: int,
    text: str,
    reply_to_message_id: int,
    message_thread_id: int | None = None,
) -> int:
    kwargs: dict[str, object] = {
        "chat_id": chat_id,
        "text": text,
        "reply_to_message_id": reply_to_message_id,
    }
    if message_thread_id is not None:
        kwargs["message_thread_id"] = int(message_thread_id)

    message = await bot.send_message(**kwargs)
    return int(message.message_id)
