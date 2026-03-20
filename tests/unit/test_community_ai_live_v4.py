from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block import repo
from services.community_block.ai_planner import plan_and_persist
from services.community_block.ai_live import maybe_send_live_reply


def apply_all_sqlite_migrations(conn: sqlite3.Connection) -> None:
    migrations_dir = Path("db/migrations_sqlite")
    for path in sorted(migrations_dir.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))


def build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    apply_all_sqlite_migrations(conn)
    bootstrap_community_layer(conn)
    conn.commit()
    return conn


def seed_post_with_reply(conn: sqlite3.Connection) -> tuple[int, dict]:
    repo.bind_chat_identity(conn, chat_key="chatlisboa", real_chat_id=-1001656765898, has_topics=True, default_topic_id=1)
    repo.enable_only_chat(conn, chat_key="chatlisboa")
    content_id = repo.create_content_item(
        conn,
        text="Как бы вы сказали это по-простому, а не языком уставшего чиновника?",
        format_type="dialogue",
        topic="documents",
        region="lisboa",
        has_question=True,
        difficulty="light",
        is_active=True,
        priority=10,
    )
    post_log_id = repo.log_post(
        conn,
        chat_id=-1001656765898,
        content_id=content_id,
        thread_root_message_id=7001,
        posted_message_id=7001,
    )
    repo.record_thread_event_rich(
        conn,
        chat_id=-1001656765898,
        post_log_id=post_log_id,
        thread_root_message_id=7001,
        message_id=7002,
        user_id=42,
        event_type="user_reply",
        message_thread_id=1,
        reply_to_message_id=7001,
        message_text="А как это реально говорят без официоза?",
    )
    repo.recompute_post_reply_stats(conn, post_log_id=post_log_id)
    repo.set_runtime_flag(conn, key="ai_live_enabled", value="1")
    repo.set_runtime_flag(conn, key="ai_reply_cooldown_seconds", value="900")
    repo.set_runtime_flag(conn, key="ai_max_generated_chars", value="220")
    repo.set_runtime_flag(conn, key="ai_fallback_to_planner_text", value="1")
    conn.commit()

    planned = plan_and_persist(conn, post_log_id=post_log_id)
    return post_log_id, planned


class DummyMessage:
    def __init__(self, message_id: int) -> None:
        self.message_id = message_id


class DummyBot:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return DummyMessage(message_id=9009)


def test_live_send_uses_generated_text_when_valid(monkeypatch) -> None:
    conn = build_conn()
    post_log_id, planned = seed_post_with_reply(conn)
    bot = DummyBot()

    class DummyGenerated:
        provider = "openai"
        model = "gpt-5"
        text = "Я бы тут сказал проще, без чиновничьего налёта."
        response_id = "resp_ok"
        raw = {"id": "resp_ok"}

    monkeypatch.setattr(
        "services.community_block.ai_live.generate_from_prompt_payload",
        lambda payload: DummyGenerated(),
    )

    async def scenario():
        out = await maybe_send_live_reply(
            conn,
            bot=bot,
            planned=planned,
            chat_id=-1001656765898,
            post_log_id=post_log_id,
            trigger_message_id=7002,
            message_thread_id=1,
        )
        assert out["status"] == "sent"
        assert out["delivery_status"] == "sent_generated"
        assert out["used_fallback"] is False

    asyncio.run(scenario())

    assert len(bot.calls) == 1
    assert bot.calls[0]["reply_to_message_id"] == 7002
    assert bot.calls[0]["message_thread_id"] == 1

    row = conn.execute(
        "SELECT delivery_status, used_fallback, sent_message_id FROM community_ai_reply_delivery_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row["delivery_status"] == "sent_generated"
    assert row["used_fallback"] == 0
    assert row["sent_message_id"] == 9009


def test_live_send_falls_back_when_generated_invalid(monkeypatch) -> None:
    conn = build_conn()
    post_log_id, planned = seed_post_with_reply(conn)
    bot = DummyBot()

    class DummyGenerated:
        provider = "openai"
        model = "gpt-5"
        text = "- первое\\n- второе"
        response_id = "resp_bad"
        raw = {"id": "resp_bad"}

    monkeypatch.setattr(
        "services.community_block.ai_live.generate_from_prompt_payload",
        lambda payload: DummyGenerated(),
    )

    async def scenario():
        out = await maybe_send_live_reply(
            conn,
            bot=bot,
            planned=planned,
            chat_id=-1001656765898,
            post_log_id=post_log_id,
            trigger_message_id=7002,
            message_thread_id=1,
        )
        assert out["status"] == "sent"
        assert out["delivery_status"] == "sent_fallback"
        assert out["used_fallback"] is True

    asyncio.run(scenario())

    assert len(bot.calls) == 1
    assert bot.calls[0]["text"] == planned["decision"]["selected_reply_text"]


def test_live_send_skips_duplicate_plan(monkeypatch) -> None:
    conn = build_conn()
    post_log_id, planned = seed_post_with_reply(conn)
    bot = DummyBot()

    class DummyGenerated:
        provider = "openai"
        model = "gpt-5"
        text = "Я бы тут сказал проще."
        response_id = "resp_ok"
        raw = {"id": "resp_ok"}

    monkeypatch.setattr(
        "services.community_block.ai_live.generate_from_prompt_payload",
        lambda payload: DummyGenerated(),
    )

    async def scenario():
        first = await maybe_send_live_reply(
            conn,
            bot=bot,
            planned=planned,
            chat_id=-1001656765898,
            post_log_id=post_log_id,
            trigger_message_id=7002,
            message_thread_id=1,
        )
        second = await maybe_send_live_reply(
            conn,
            bot=bot,
            planned=planned,
            chat_id=-1001656765898,
            post_log_id=post_log_id,
            trigger_message_id=7002,
            message_thread_id=1,
        )
        assert first["status"] == "sent"
        assert second["status"] == "skipped"
        assert second["reason"] == "delivery_already_exists"

    asyncio.run(scenario())

    assert len(bot.calls) == 1
