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
        first_name="Bin",
        last_name="Exposure",
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


def test_selector_prefers_less_burned_bin() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db
        repo = VocabRepository(conn)

        await repo.seed_demo_items_if_empty()

        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id = 911301")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id = 911301")
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 911301))")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 911301))")
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 911301))")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 911301)")
        await conn.execute("DELETE FROM mode_runs WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 911301)")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 911301")
        await conn.execute("DELETE FROM vocab_item_exposure")
        await conn.commit()

        burned_ids = [
            await _get_item_id_by_lemma(conn, "casa"),
            await _get_item_id_by_lemma(conn, "livro"),
            await _get_item_id_by_lemma(conn, "água"),
        ]
        for item_id in burned_ids:
            for _ in range(25):
                await repo.mark_item_shown_global(item_id=item_id)

        engine = VocabEngine()
        tg_user = build_user(911301)
        await engine.start_attempt(
            tg_user=tg_user,
            prior_payload={"source": "bin_exposure_selector_test"},
        )

        user_id = await repo.upsert_user_from_telegram(tg_user)
        active = await repo.get_active_vocab_attempt(user_id=user_id)
        assert active is not None

        selector = VocabSelector(conn)
        picked = await selector.pick_next_item(attempt_id=int(active["id"]))
        assert picked is not None
        assert int(picked["id"]) not in burned_ids

        # Contract of baseline selector:
        # avoid highly-burned items when possible, but do not globally ban 1K
        # unless there is an explicit bin-level policy for that.
        cursor = await conn.execute(
            """
            SELECT COALESCE(shown_count, 0) AS shown_count
            FROM vocab_item_exposure
            WHERE item_id = ?
            """,
            (int(picked["id"]),),
        )
        exposure_row = await cursor.fetchone()
        picked_shown = int(exposure_row["shown_count"] or 0) if exposure_row is not None else 0
        assert picked_shown < 25

        await close_container()

    asyncio.run(run())
