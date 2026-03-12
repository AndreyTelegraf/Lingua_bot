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
        first_name="Quota",
        last_name="Selector",
        username=f"user_{user_id}",
        language_code="ru",
    )


def test_selector_prefers_underfilled_pos() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db

        await conn.execute("DELETE FROM vocab_choices WHERE item_id IN (SELECT id FROM vocab_items WHERE lemma IN ('teste_a1_cap', 'teste_a2_cap'))")
        await conn.execute("DELETE FROM vocab_items WHERE lemma IN ('teste_a1_cap', 'teste_a2_cap')")
        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id = 910601")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id = 910601")
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 910601))")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 910601))")
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 910601))")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 910601)")
        await conn.execute("DELETE FROM mode_runs WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 910601)")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 910601")
        await conn.execute("DELETE FROM vocab_item_exposure")
        await conn.commit()

        repo = VocabRepository(conn)
        await repo.seed_demo_items_if_empty()

        engine = VocabEngine()
        tg_user = build_user(910601)

        await engine.start_attempt(
            tg_user=tg_user,
            prior_payload={"source": "selector_quota_test"},
        )

        q1 = await engine.prepare_next_question(tg_user=tg_user)
        assert q1.item_id > 0

        await engine.confirm_question_shown(
            tg_user=tg_user,
            callback_token=q1.callback_token,
        )

        cursor = await conn.execute(
            "SELECT lemma, pos, bin_name FROM vocab_items WHERE id = ?",
            (q1.item_id,),
        )
        picked_row = await cursor.fetchone()
        assert picked_row is not None
        assert str(picked_row["pos"]) == "noun"

        cursor = await conn.execute(
            "SELECT id FROM users WHERE telegram_user_id = ?",
            (910601,),
        )
        user_row = await cursor.fetchone()
        assert user_row is not None
        user_id = int(user_row["id"])

        active = await repo.get_active_vocab_attempt(user_id=user_id)
        assert active is not None

        selector = VocabSelector(conn)
        next_item = await selector.pick_next_item(attempt_id=int(active["id"]))
        assert next_item is not None
        assert int(next_item["id"]) != q1.item_id
        assert str(next_item["pos"]) == "verb"
        assert str(next_item["bin_name"]) == "2K"

        await close_container()

    asyncio.run(run())
