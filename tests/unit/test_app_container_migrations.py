from __future__ import annotations

from app import container as container_mod


class DummyConn:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def test_init_container_applies_migrations_before_open_db(monkeypatch) -> None:
    calls: list[str] = []
    dummy = DummyConn()

    async def fake_apply_migrations():
        calls.append("apply_migrations")

    async def fake_open_db():
        calls.append("open_db")
        return dummy

    monkeypatch.setattr(container_mod, "apply_migrations", fake_apply_migrations)
    monkeypatch.setattr(container_mod, "open_db", fake_open_db)
    container_mod.container.db = None

    import asyncio
    asyncio.run(container_mod.init_container())

    assert calls == ["apply_migrations", "open_db"]
    assert container_mod.container.db is dummy

    asyncio.run(container_mod.close_container())
    assert dummy.closed is True
    assert container_mod.container.db is None


def test_init_container_does_not_reopen_existing_db(monkeypatch) -> None:
    calls: list[str] = []
    existing = DummyConn()

    async def fake_apply_migrations():
        calls.append("apply_migrations")

    async def fake_open_db():
        calls.append("open_db")
        raise AssertionError("open_db should not be called")

    monkeypatch.setattr(container_mod, "apply_migrations", fake_apply_migrations)
    monkeypatch.setattr(container_mod, "open_db", fake_open_db)
    container_mod.container.db = existing

    import asyncio
    asyncio.run(container_mod.init_container())

    assert calls == ["apply_migrations"]
    assert container_mod.container.db is existing

    container_mod.container.db = None
