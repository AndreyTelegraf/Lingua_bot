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


def test_runtime_prevents_same_content_across_chats_in_same_tick(monkeypatch) -> None:
    conn = build_conn()
    runtime_conn = NoCloseConn(conn)

    targets = [
        ("chatalgarve", -1001690275466, None),
        ("chatlisboa", -1001656765898, 9001),
        ("chatporto", -1001719116315, None),
        ("chatleiria", -1001227461571, None),
    ]

    for key, chat_id, topic_id in targets:
        repo.bind_chat_identity(
            conn,
            chat_key=key,
            real_chat_id=chat_id,
            has_topics=bool(topic_id),
            default_topic_id=topic_id,
        )

    for key, _, _ in targets:
        conn.execute("""
            UPDATE community_chats
            SET is_enabled = 1,
                daily_post_time = '00:00',
                cooldown_hours = 24,
                last_posted_at = NULL
            WHERE chat_key = ?
        """, (key,))

    conn.execute("""
        INSERT INTO community_runtime_config(key, value_text)
        VALUES ('global_enabled', '1')
        ON CONFLICT(key) DO UPDATE SET value_text='1', updated_at=CURRENT_TIMESTAMP
    """)
    conn.execute("""
        INSERT INTO community_runtime_config(key, value_text)
        VALUES ('dry_run_override', '0')
        ON CONFLICT(key) DO UPDATE SET value_text='0', updated_at=CURRENT_TIMESTAMP
    """)
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
    monkeypatch.setattr(runtime_mod, "utc_now", lambda: datetime(2026, 3, 19, 0, 5, tzinfo=UTC))

    sent_calls = []

    class DummySession:
        async def close(self) -> None:
            return None

    class DummyBot:
        def __init__(self, token: str) -> None:
            self.token = token
            self.session = DummySession()

    seq = {"n": 1000}

    async def fake_send_post(bot, *, chat_id: int, text: str, default_topic_id=None) -> int:
        seq["n"] += 1
        sent_calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "default_topic_id": default_topic_id,
                "message_id": seq["n"],
            }
        )
        return seq["n"]

    monkeypatch.setattr(runtime_mod, "Bot", DummyBot)
    monkeypatch.setattr(runtime_mod, "send_post", fake_send_post)

    async def scenario():
        await runtime_mod._maybe_send_scheduled_posts(dry_run_default=True)

    asyncio.run(scenario())

    rows = conn.execute("""
        SELECT chat_id, content_id
        FROM community_post_log
        ORDER BY id
    """).fetchall()

    content_ids = [int(r["content_id"]) for r in rows]

    # bootstrap seeds only 3 default content items, so anti-dup should yield
    # 3 unique sends and 1 no_candidate instead of allowing a duplicate.
    assert len(rows) == 3, f"expected 3 unique sends with current seeded bank, got {len(rows)}"
    assert len(sent_calls) == 3, f"expected 3 sends with current seeded bank, got {len(sent_calls)}"
    assert len(set(content_ids)) == 3, f"expected all sent content_ids to be unique, got {content_ids}"

    # chatlisboa should preserve topic routing when it is one of the sent chats
    lisboa_calls = [c for c in sent_calls if c["chat_id"] == -1001656765898]
    if lisboa_calls:
        assert lisboa_calls[0]["default_topic_id"] == 9001
