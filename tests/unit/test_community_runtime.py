from __future__ import annotations

import asyncio
import sqlite3

from services.community_block import runtime as runtime_mod


class DummyConn:
    def __init__(self) -> None:
        self.committed = False
        self.closed = False
        self.row_factory = None
        self.executed: list[str] = []

    def execute(self, sql: str):
        self.executed.append(sql)
        return self

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


def test_start_community_runtime_disabled_by_feature_flag(monkeypatch) -> None:
    class Settings:
        feature_community_enabled = False
        community_dry_run = True
        community_tick_seconds = 60
        app_env = "test"
        db_path = ":memory:"

    monkeypatch.setattr(runtime_mod, "get_settings", lambda: Settings())

    started = asyncio.run(runtime_mod.start_community_runtime())
    assert started is False


def test_open_runtime_db_returns_sqlite_connection(monkeypatch, tmp_path) -> None:
    db_path_str = str(tmp_path / "community_runtime_test.db")

    class Settings:
        feature_community_enabled = True
        community_dry_run = True
        community_tick_seconds = 60
        app_env = "test"
        db_path = db_path_str

    monkeypatch.setattr(runtime_mod, "get_settings", lambda: Settings())

    conn = runtime_mod._open_runtime_db()
    try:
        assert isinstance(conn, sqlite3.Connection)
        row = conn.execute("SELECT 1").fetchone()
        assert row[0] == 1
    finally:
        conn.close()


def test_start_and_stop_community_runtime(monkeypatch) -> None:
    class Settings:
        feature_community_enabled = True
        community_dry_run = True
        community_tick_seconds = 5
        app_env = "test"
        db_path = ":memory:"

    conn = DummyConn()

    monkeypatch.setattr(runtime_mod, "get_settings", lambda: Settings())
    monkeypatch.setattr(runtime_mod, "_open_runtime_db", lambda: conn)
    monkeypatch.setattr(runtime_mod, "bootstrap_community_layer", lambda db: None)
    monkeypatch.setattr(runtime_mod.repo, "get_runtime_flag", lambda db, key, default=None: default)
    monkeypatch.setattr(runtime_mod.repo, "list_all_chats", lambda db: [])
    monkeypatch.setattr(runtime_mod, "choose_post_candidate", lambda db, chat, recent_messages_count=0, dry_run=True: None)

    async def scenario():
        started = await runtime_mod.start_community_runtime()
        assert started is True
        assert runtime_mod._runtime.task is not None
        await asyncio.sleep(0.05)
        await runtime_mod.stop_community_runtime()
        assert runtime_mod._runtime.task is None
        assert runtime_mod._runtime.stop_event is None
        assert conn.committed is True
        assert conn.closed is True
        assert any("PRAGMA foreign_keys" in x for x in conn.executed) is False

    asyncio.run(scenario())
