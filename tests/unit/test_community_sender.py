from __future__ import annotations

import asyncio

from services.community_block.sender import send_post


class DummyMessage:
    def __init__(self, message_id: int) -> None:
        self.message_id = message_id


class DummyBot:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return DummyMessage(message_id=321)


def test_send_post_without_topic() -> None:
    bot = DummyBot()

    async def scenario():
        message_id = await send_post(
            bot,
            chat_id=-1001,
            text="hello",
            default_topic_id=None,
        )
        assert message_id == 321

    asyncio.run(scenario())

    assert bot.calls == [
        {
            "chat_id": -1001,
            "text": "hello",
        }
    ]


def test_send_post_with_topic() -> None:
    bot = DummyBot()

    async def scenario():
        message_id = await send_post(
            bot,
            chat_id=-1002,
            text="hello topic",
            default_topic_id=777,
        )
        assert message_id == 321

    asyncio.run(scenario())

    assert bot.calls == [
        {
            "chat_id": -1002,
            "text": "hello topic",
            "message_thread_id": 777,
        }
    ]
