import asyncio

from aiogram.types import User

from app.container import close_container, init_container, container
from modes.vocab.repo import VocabRepository


def build_user(user_id: int) -> User:
    return User(
        id=user_id,
        is_bot=False,
        first_name="Repo",
        last_name="State",
        username=f"user_{user_id}",
        language_code="ru",
    )


def test_vocab_repo_v2_selector_state_and_counters() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db
        repo = VocabRepository(conn)

        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 910401))")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 910401))")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 910401)")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 910401)")
        await conn.execute("DELETE FROM mode_runs WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = 910401)")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 910401")
        await conn.commit()

        await repo.seed_demo_items_if_empty()

        user_id = await repo.upsert_user_from_telegram(build_user(910401))
        mode_run_id = await repo.create_mode_run(user_id=user_id, prior_payload={"source": "repo_v2_test"})
        attempt_id = await repo.create_vocab_attempt(mode_run_id=mode_run_id, user_id=user_id)

        state = await repo.get_selector_state(attempt_id=attempt_id)
        assert state.shown_item_ids == []
        assert state.pos_counters == {}
        assert state.cefr_counters == {}
        assert state.bin_counters == {}
        assert state.current_item_meta == {}

        state.mark_item_shown(
            item_id=1,
            pos="noun",
            level="A1",
            bin_name="1K",
            step_index=1,
        )
        await repo.save_selector_state(attempt_id=attempt_id, state=state)

        state2 = await repo.get_selector_state(attempt_id=attempt_id)
        assert state2.shown_item_ids == [1]
        assert state2.pos_counters["noun"] == 1
        assert state2.cefr_counters["A1"] == 1
        assert state2.bin_counters["1K"] == 1
        assert int(state2.current_item_meta["item_id"]) == 1

        await repo.bump_attempt_after_answer(
            attempt_id=attempt_id,
            is_correct=True,
            is_dont_know=False,
        )

        stats = await repo.get_attempt_stats(attempt_id=attempt_id)
        assert stats is not None
        assert int(stats["questions_answered"]) == 1
        assert int(stats["correct_count"]) == 1
        assert int(stats["dont_know_count"]) == 0
        assert int(stats["hard_reject_streak"]) == 0

        await repo.bump_attempt_reject(attempt_id=attempt_id)
        stats = await repo.get_attempt_stats(attempt_id=attempt_id)
        assert stats is not None
        assert int(stats["total_reject_count"]) == 1
        assert int(stats["hard_reject_streak"]) == 1

        await close_container()

    asyncio.run(run())
