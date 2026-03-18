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


def test_has_post_for_chat_on_date() -> None:
    conn = build_conn()
    repo.bind_chat_identity(conn, chat_key="chatalgarve", real_chat_id=-1001690275466)
    repo.enable_only_chat(conn, chat_key="chatalgarve")
    content_id = 1
    repo.log_post(
        conn,
        chat_id=-1001690275466,
        content_id=content_id,
        thread_root_message_id=123,
        posted_message_id=123,
    )
    conn.commit()

    row = conn.execute("SELECT date(posted_at) FROM community_post_log ORDER BY id DESC LIMIT 1").fetchone()
    assert row is not None
    yyyy_mm_dd = row[0]

    assert repo.has_post_for_chat_on_date(conn, chat_id=-1001690275466, yyyy_mm_dd=yyyy_mm_dd) is True
    conn.close()


def test_maybe_send_scheduled_posts_dry_run_does_not_write_post_log(monkeypatch) -> None:
    conn = build_conn()
    runtime_conn = NoCloseConn(conn)

    repo.bind_chat_identity(conn, chat_key="chatalgarve", real_chat_id=-1001690275466)
    repo.enable_only_chat(conn, chat_key="chatalgarve")
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

    async def scenario():
        await runtime_mod._maybe_send_scheduled_posts(dry_run=True)

    asyncio.run(scenario())

    count = conn.execute("SELECT COUNT(*) FROM community_post_log").fetchone()[0]
    assert count == 0
    conn.close()


def test_maybe_send_scheduled_posts_real_send_writes_post_log(monkeypatch) -> None:
    conn = build_conn()
    runtime_conn = NoCloseConn(conn)

    repo.bind_chat_identity(conn, chat_key="chatalgarve", real_chat_id=-1001690275466)
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
        return 777

    monkeypatch.setattr(runtime_mod, "Bot", DummyBot)
    monkeypatch.setattr(runtime_mod, "send_post", fake_send_post)

    async def scenario():
        await runtime_mod._maybe_send_scheduled_posts(dry_run=False)

    asyncio.run(scenario())

    assert len(sent_calls) == 1
    row = conn.execute(
        "SELECT chat_id, posted_message_id FROM community_post_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row["chat_id"] == -1001690275466
    assert row["posted_message_id"] == 777
    conn.close()


def test_maybe_send_scheduled_posts_skips_duplicate_same_day(monkeypatch) -> None:
    conn = build_conn()
    runtime_conn = NoCloseConn(conn)

    repo.bind_chat_identity(conn, chat_key="chatalgarve", real_chat_id=-1001690275466)
    repo.enable_only_chat(conn, chat_key="chatalgarve")
    conn.execute("UPDATE community_chats SET daily_post_time = '11:00' WHERE chat_key = 'chatalgarve'")
    repo.log_post(
        conn,
        chat_id=-1001690275466,
        content_id=1,
        thread_root_message_id=888,
        posted_message_id=888,
    )
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

    from datetime import datetime
    row = conn.execute("SELECT date(posted_at) FROM community_post_log ORDER BY id DESC LIMIT 1").fetchone()
    yyyy_mm_dd = row[0]
    monkeypatch.setattr(runtime_mod, "utc_now", lambda: datetime.fromisoformat(f"{yyyy_mm_dd}T11:10:00+00:00"))

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
        return 999

    monkeypatch.setattr(runtime_mod, "Bot", DummyBot)
    monkeypatch.setattr(runtime_mod, "send_post", fake_send_post)

    async def scenario():
        await runtime_mod._maybe_send_scheduled_posts(dry_run=False)

    asyncio.run(scenario())

    assert sent_calls == []
    count = conn.execute("SELECT COUNT(*) FROM community_post_log").fetchone()[0]
    assert count == 1
    conn.close()
