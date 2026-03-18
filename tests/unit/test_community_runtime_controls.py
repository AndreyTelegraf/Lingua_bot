from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from services.community_block import repo
from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block import runtime as runtime_mod


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


class NoCloseConn:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self) -> None:
        return None


def test_runtime_respects_global_enabled_zero(monkeypatch) -> None:
    conn = build_conn()
    runtime_conn = NoCloseConn(conn)

    repo.set_runtime_flag(conn, key="global_enabled", value="0")
    repo.enable_only_chat(conn, chat_key="chatalgarve")
    conn.execute("UPDATE community_chats SET daily_post_time = '11:00' WHERE chat_key = 'chatalgarve'")
    conn.commit()

    class Settings:
        app_env = "test"
        bot_token = "dummy"
        db_path = ":memory:"
        feature_community_enabled = True
        community_dry_run = False
        community_tick_seconds = 60

    monkeypatch.setattr(runtime_mod, "get_settings", lambda: Settings())
    monkeypatch.setattr(runtime_mod, "_open_runtime_db", lambda: runtime_conn)

    from datetime import UTC, datetime
    monkeypatch.setattr(runtime_mod, "utc_now", lambda: datetime(2026, 3, 17, 11, 5, tzinfo=UTC))

    sent_calls = []

    class DummySession:
        async def close(self) -> None:
            return None

    class DummyBot:
        def __init__(self, token: str) -> None:
            self.token = token
            self.session = DummySession()

    async def fake_send_post(bot, *, chat_id: int, text: str, default_topic_id=None) -> int:
        sent_calls.append((chat_id, text, default_topic_id))
        return 111

    monkeypatch.setattr(runtime_mod, "Bot", DummyBot)
    monkeypatch.setattr(runtime_mod, "send_post", fake_send_post)

    async def scenario():
        await runtime_mod._maybe_send_scheduled_posts(dry_run_default=False)

    asyncio.run(scenario())

    assert sent_calls == []
    assert conn.execute("SELECT COUNT(*) FROM community_post_log").fetchone()[0] == 0
    conn.close()


def test_runtime_respects_dry_run_override_zero(monkeypatch) -> None:
    conn = build_conn()
    runtime_conn = NoCloseConn(conn)

    repo.enable_only_chat(conn, chat_key="chatalgarve")
    repo.set_runtime_flag(conn, key="dry_run_override", value="0")
    conn.execute("UPDATE community_chats SET daily_post_time = '11:00' WHERE chat_key = 'chatalgarve'")
    conn.commit()

    class Settings:
        app_env = "test"
        bot_token = "dummy"
        db_path = ":memory:"
        feature_community_enabled = True
        community_dry_run = True
        community_tick_seconds = 60

    monkeypatch.setattr(runtime_mod, "get_settings", lambda: Settings())
    monkeypatch.setattr(runtime_mod, "_open_runtime_db", lambda: runtime_conn)

    from datetime import UTC, datetime
    monkeypatch.setattr(runtime_mod, "utc_now", lambda: datetime(2026, 3, 17, 11, 5, tzinfo=UTC))

    sent_calls = []

    class DummySession:
        async def close(self) -> None:
            return None

    class DummyBot:
        def __init__(self, token: str) -> None:
            self.token = token
            self.session = DummySession()

    async def fake_send_post(bot, *, chat_id: int, text: str, default_topic_id=None) -> int:
        sent_calls.append((chat_id, text, default_topic_id))
        return 222

    monkeypatch.setattr(runtime_mod, "Bot", DummyBot)
    monkeypatch.setattr(runtime_mod, "send_post", fake_send_post)

    async def scenario():
        await runtime_mod._maybe_send_scheduled_posts(dry_run_default=True)

    asyncio.run(scenario())

    assert len(sent_calls) == 1
    row = conn.execute(
        "SELECT posted_message_id FROM community_post_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row["posted_message_id"] == 222
    conn.close()
