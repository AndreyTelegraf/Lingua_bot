from __future__ import annotations

import asyncio

from services.community_block import runtime as runtime_mod


class DummyConn:
    async def close(self) -> None:
        return None


def test_start_community_runtime_disabled_by_feature_flag(monkeypatch) -> None:
    class Settings:
        feature_community_enabled = False
        community_dry_run = True
        community_tick_seconds = 60
        app_env = "test"

    monkeypatch.setattr(runtime_mod, "get_settings", lambda: Settings())

    started = asyncio.run(runtime_mod.start_community_runtime())
    assert started is False


def test_start_and_stop_community_runtime(monkeypatch) -> None:
    class Settings:
        feature_community_enabled = True
        community_dry_run = True
        community_tick_seconds = 5
        app_env = "test"

    monkeypatch.setattr(runtime_mod, "get_settings", lambda: Settings())
    monkeypatch.setattr(runtime_mod, "open_db", lambda: _dummy_open_db())
    monkeypatch.setattr(runtime_mod.repo, "get_runtime_flag", lambda conn, key, default=None: default)
    monkeypatch.setattr(runtime_mod.repo, "list_enabled_chats", lambda conn: [])

    async def scenario():
        started = await runtime_mod.start_community_runtime()
        assert started is True
        assert runtime_mod._runtime.task is not None
        await asyncio.sleep(0.05)
        await runtime_mod.stop_community_runtime()
        assert runtime_mod._runtime.task is None
        assert runtime_mod._runtime.stop_event is None

    async def _dummy_open_db():
        return DummyConn()

    asyncio.run(scenario())
