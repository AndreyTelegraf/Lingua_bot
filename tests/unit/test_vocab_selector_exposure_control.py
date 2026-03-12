import asyncio

from aiogram.types import User

from app.container import close_container, init_container, container
from modes.vocab.engine import VocabEngine
from modes.vocab.repo import VocabRepository
from modes.vocab.selector import VocabSelector


def build_user(user_id: int) -> User:
    return User(
        id=user_id,
        is_bot=False,
        first_name="Exposure",
        last_name="Selector",
        username=f"user_{user_id}",
        language_code="ru",
    )


async def _get_item_id_by_lemma(conn, lemma: str) -> int:
    cursor = await conn.execute(
        "SELECT id FROM vocab_items WHERE lemma = ? ORDER BY id LIMIT 1",
        (lemma,),
    )
    row = await cursor.fetchone()
    assert row is not None, f"item_not_found:{lemma}"
    return int(row["id"])


def test_selector_prefers_lower_global_shown_count() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db
        repo = VocabRepository(conn)

        await repo.seed_demo_items_if_empty()

        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id = 911101")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id = 911101")
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 911101))")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 911101))")
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 911101))")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 911101)")
        await conn.execute("DELETE FROM mode_runs WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 911101)")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 911101")
        await conn.execute("DELETE FROM vocab_item_exposure")
        await conn.commit()

        burned_item_id = await _get_item_id_by_lemma(conn, "água")

        for _ in range(20):
            await repo.mark_item_shown_global(item_id=burned_item_id)

        engine = VocabEngine()
        tg_user = build_user(911101)
        await engine.start_attempt(
            tg_user=tg_user,
            prior_payload={"source": "exposure_selector_test"},
        )

        user_id = await repo.upsert_user_from_telegram(tg_user)
        active = await repo.get_active_vocab_attempt(user_id=user_id)
        assert active is not None

        selector = VocabSelector(conn)
        picked = await selector.pick_next_item(attempt_id=int(active["id"]))
        assert picked is not None
        assert int(picked["id"]) != burned_item_id

        await close_container()

    asyncio.run(run())
