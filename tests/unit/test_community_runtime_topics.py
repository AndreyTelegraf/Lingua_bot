from __future__ import annotations

import asyncio
import sqlite3

import services.community_block.runtime as runtime_mod
from services.community_block import bootstrap, repo


class NoCloseConn:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self) -> None:
        return None


def build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS community_runtime_config (
            key TEXT PRIMARY KEY,
            value_text TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS community_chats (
            chat_id INTEGER NOT NULL UNIQUE,
            chat_key TEXT NOT NULL UNIQUE,
            chat_type TEXT NOT NULL,
            region TEXT,
            has_topics INTEGER NOT NULL DEFAULT 0,
            default_topic_id INTEGER,
            is_enabled INTEGER NOT NULL DEFAULT 0,
            daily_post_time TEXT NOT NULL DEFAULT '11:00',
            max_posts_per_day INTEGER NOT NULL DEFAULT 1,
            cooldown_hours INTEGER NOT NULL DEFAULT 24,
            last_posted_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS community_content_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            format_type TEXT NOT NULL,
            topic TEXT,
            region TEXT,
            has_question INTEGER NOT NULL DEFAULT 1,
            difficulty TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 50,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS community_post_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            content_id INTEGER NOT NULL,
            thread_root_message_id INTEGER,
            posted_message_id INTEGER NOT NULL,
            posted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        '''
    )
    bootstrap.bootstrap_community_layer(conn)
    return conn


def test_runtime_sends_into_topic_when_default_topic_present(monkeypatch) -> None:
    conn = build_conn()
    runtime_conn = NoCloseConn(conn)

    repo.bind_chat_identity(
        conn,
        chat_key="chatlisboa",
        real_chat_id=-1001656765898,
        has_topics=True,
        default_topic_id=9001,
    )
    repo.enable_only_chat(conn, chat_key="chatlisboa")
    conn.execute("UPDATE community_chats SET daily_post_time = '00:00', cooldown_hours = 0, last_posted_at = '2026-03-16 00:00:00' WHERE chat_key = 'chatlisboa'")
    conn.execute("INSERT OR REPLACE INTO community_runtime_config(key, value_text) VALUES ('global_enabled', '1')")
    conn.execute("INSERT OR REPLACE INTO community_runtime_config(key, value_text) VALUES ('dry_run_override', '0')")
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
    monkeypatch.setattr(runtime_mod, "utc_now", lambda: datetime(2026, 3, 18, 0, 1, tzinfo=UTC))

    sent_calls = []

    class DummySession:
        async def close(self) -> None:
            return None

    class DummyBot:
        def __init__(self, token: str) -> None:
            self.token = token
            self.session = DummySession()

    async def fake_send_post(bot, *, chat_id: int, text: str, default_topic_id=None) -> int:
        sent_calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "default_topic_id": default_topic_id,
            }
        )
        return 555

    monkeypatch.setattr(runtime_mod, "Bot", DummyBot)
    monkeypatch.setattr(runtime_mod, "send_post", fake_send_post)

    async def scenario():
        await runtime_mod._maybe_send_scheduled_posts(dry_run_default=True)

    asyncio.run(scenario())

    assert len(sent_calls) == 1
    assert sent_calls[0]["chat_id"] == -1001656765898
    assert sent_calls[0]["default_topic_id"] == 9001

    row = conn.execute(
        "SELECT posted_message_id FROM community_post_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert int(row[0]) == 555
