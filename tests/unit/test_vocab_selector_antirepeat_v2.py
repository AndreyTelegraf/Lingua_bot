import asyncio
import os
from types import SimpleNamespace

import aiosqlite

from modes.vocab.repo import VocabRepository
from modes.vocab.selector import VocabSelector


def test_selector_antirepeat_stage_order() -> None:
    async def run() -> None:
        old_prev = os.environ.get("VOCAB_SELECTOR_PREVIOUS_ATTEMPTS_EXCLUDE")
        old_days = os.environ.get("VOCAB_SELECTOR_USER_ITEM_COOLDOWN_DAYS")
        old_fb = os.environ.get("VOCAB_SELECTOR_MIN_RECENT_ATTEMPTS_FALLBACK")

        os.environ["VOCAB_SELECTOR_PREVIOUS_ATTEMPTS_EXCLUDE"] = "3"
        os.environ["VOCAB_SELECTOR_USER_ITEM_COOLDOWN_DAYS"] = "30"
        os.environ["VOCAB_SELECTOR_MIN_RECENT_ATTEMPTS_FALLBACK"] = "1"

        try:
            selector = VocabSelector(conn=None)  # type: ignore[arg-type]
            selector.repo = SimpleNamespace(
                get_selector_state=lambda attempt_id: _awaitable(SimpleNamespace(shown_item_ids=[1, 2])),
                get_recent_attempt_item_ids=lambda attempt_id, previous_attempts_limit: _awaitable(
                    [10, 11, 12] if previous_attempts_limit == 3 else [99]
                ),
                get_recent_user_shown_item_ids=lambda attempt_id, days: _awaitable([20, 21]),
            )

            calls = []

            async def fake_fetch_candidates(*, excluded_ids, apply_cooldown):
                calls.append((list(excluded_ids), apply_cooldown))
                if excluded_ids == [1, 2, 10, 11, 12, 20, 21]:
                    return []
                if excluded_ids == [1, 2, 20, 21]:
                    return [{"id": 777}]
                return []

            async def fake_pick_from_rows(*, rows, state):
                return rows[0] if rows else None

            selector._fetch_candidates = fake_fetch_candidates  # type: ignore[method-assign]
            selector._pick_from_rows = fake_pick_from_rows  # type: ignore[method-assign]

            picked = await selector.pick_next_item(attempt_id=555)
            assert picked is not None
            assert int(picked["id"]) == 777

            assert calls[0] == ([1, 2, 10, 11, 12, 20, 21], True)
            assert calls[1] == ([1, 2, 20, 21], True)
        finally:
            _restore_env("VOCAB_SELECTOR_PREVIOUS_ATTEMPTS_EXCLUDE", old_prev)
            _restore_env("VOCAB_SELECTOR_USER_ITEM_COOLDOWN_DAYS", old_days)
            _restore_env("VOCAB_SELECTOR_MIN_RECENT_ATTEMPTS_FALLBACK", old_fb)

    asyncio.run(run())


def test_repo_recent_user_shown_item_ids_filters_by_user_days_and_current_attempt() -> None:
    async def run() -> None:
        conn = await aiosqlite.connect(":memory:")
        conn.row_factory = aiosqlite.Row
        try:
            await conn.executescript(
                """
                CREATE TABLE vocab_attempts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL
                );

                CREATE TABLE vocab_attempt_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id INTEGER NOT NULL,
                    item_id INTEGER,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

            await conn.executemany(
                "INSERT INTO vocab_attempts (id, user_id) VALUES (?, ?)",
                [
                    (100, 1),  # current attempt
                    (101, 1),  # same user recent
                    (102, 1),  # same user old
                    (103, 2),  # other user
                ],
            )

            await conn.executemany(
                """
                INSERT INTO vocab_attempt_events (attempt_id, item_id, event_type, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (100, 500, "shown", "2026-03-15 00:00:00"),          # current attempt, exclude
                    (101, 501, "shown", "2026-03-10 00:00:00"),          # recent, include
                    (101, 502, "question_shown", "2026-03-12 00:00:00"), # recent, include
                    (101, 503, "answer", "2026-03-12 00:00:00"),         # wrong event, exclude
                    (102, 504, "shown", "2025-12-01 00:00:00"),          # too old, exclude
                    (103, 505, "shown", "2026-03-12 00:00:00"),          # other user, exclude
                ],
            )
            await conn.commit()

            repo = VocabRepository(conn)
            ids = await repo.get_recent_user_shown_item_ids(attempt_id=100, days=30)
            assert ids == [501, 502]
        finally:
            await conn.close()

    asyncio.run(run())


async def _awaitable(value):
    return value


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
