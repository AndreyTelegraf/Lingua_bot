import asyncio

from aiogram.types import User

from app.container import close_container, init_container, container
from domain.attempts.repository import FsmRuntimeRepository
from domain.shared.enums import ModeCode
from modes.vocab.engine import VocabEngine



async def _get_correct_choice_id(conn, item_id: int) -> int:
    cursor = await conn.execute(
        "SELECT id FROM vocab_choices WHERE item_id = ? AND is_correct = 1",
        (item_id,),
    )
    row = await cursor.fetchone()
    assert row is not None
    return int(row["id"])


def build_user(user_id: int) -> User:
    return User(
        id=user_id,
        is_bot=False,
        first_name="Finish",
        last_name="Pipeline",
        username=f"user_{user_id}",
        language_code="ru",
    )


def test_finish_rejected_when_limit_not_reached_and_items_remain() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db

        await conn.execute("DELETE FROM vocab_choices WHERE item_id IN (SELECT id FROM vocab_items WHERE lemma IN ('teste_a1_cap', 'teste_a2_cap'))")
        await conn.execute("DELETE FROM vocab_items WHERE lemma IN ('teste_a1_cap', 'teste_a2_cap')")
        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id = 910303")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id = 910303")
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910303)")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910303)")
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910303)")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id = 910303")
        await conn.execute("DELETE FROM mode_results WHERE user_id = 910303")
        await conn.execute("DELETE FROM mode_runs WHERE user_id = 910303")
        await conn.execute("DELETE FROM user_mode_priors WHERE user_id = 910303")
        await conn.execute("DELETE FROM user_assessment_profile WHERE user_id = 910303")
        await conn.execute("DELETE FROM user_profiles WHERE user_id = 910303")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 910303")
        await conn.commit()

        engine = VocabEngine()
        tg_user = build_user(910303)

        await engine.start_attempt(
            tg_user=tg_user,
            prior_payload={"source": "finish_test_reject"},
        )

        q1 = await engine.prepare_next_question(tg_user=tg_user)
        await engine.confirm_question_shown(
            tg_user=tg_user,
            callback_token=q1.callback_token,
        )
        q1_correct_choice_id = await _get_correct_choice_id(conn, q1.item_id)
        await engine.submit_answer(
            tg_user=tg_user,
            selected_choice_id=q1_correct_choice_id,
            callback_token=q1.callback_token,
        )

        q2 = await engine.prepare_next_question(tg_user=tg_user)
        await engine.confirm_question_shown(
            tg_user=tg_user,
            callback_token=q2.callback_token,
        )
        q2_correct_choice_id = await _get_correct_choice_id(conn, q2.item_id)
        await engine.submit_answer(
            tg_user=tg_user,
            selected_choice_id=q2_correct_choice_id,
            callback_token=q2.callback_token,
        )

        try:
            await engine.finish_attempt(
                tg_user=tg_user,
                completion_reason="stop_rule_exhausted_items",
            )
        except RuntimeError as exc:
            assert str(exc) == "finish_not_allowed_items_remaining"
        else:
            raise AssertionError("finish_attempt unexpectedly succeeded while limit not reached")

        user_row = await conn.execute(
            "SELECT id FROM users WHERE telegram_user_id = ?",
            (910303,),
        )
        user_db = await user_row.fetchone()
        assert user_db is not None

        fsm_repo = FsmRuntimeRepository(conn)
        state = await fsm_repo.get_state(ModeCode.VOCAB, int(user_db["id"]))
        assert state is not None
        assert state.status.value == "selecting"

        await engine.abort_attempt(
            tg_user=tg_user,
            completion_reason="finish_test_cleanup",
        )

        await close_container()

    asyncio.run(run())


def test_finish_allowed_when_question_limit_reached_even_if_items_remain() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db

        await conn.execute("DELETE FROM vocab_choices WHERE item_id IN (SELECT id FROM vocab_items WHERE lemma IN ('teste_a1_cap', 'teste_a2_cap'))")
        await conn.execute("DELETE FROM vocab_items WHERE lemma IN ('teste_a1_cap', 'teste_a2_cap')")
        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id = 910304")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id = 910304")
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910304)")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910304)")
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910304)")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id = 910304")
        await conn.execute("DELETE FROM mode_results WHERE user_id = 910304")
        await conn.execute("DELETE FROM mode_runs WHERE user_id = 910304")
        await conn.execute("DELETE FROM user_mode_priors WHERE user_id = 910304")
        await conn.execute("DELETE FROM user_assessment_profile WHERE user_id = 910304")
        await conn.execute("DELETE FROM user_profiles WHERE user_id = 910304")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 910304")
        await conn.commit()

        engine = VocabEngine()
        tg_user = build_user(910304)

        started = await engine.start_attempt(
            tg_user=tg_user,
            prior_payload={"source": "finish_test_limit"},
        )

        await conn.execute(
            "UPDATE vocab_attempts SET question_limit = 2 WHERE id = ?",
            (started.vocab_attempt_id,),
        )
        await conn.commit()

        q1 = await engine.prepare_next_question(tg_user=tg_user)
        await engine.confirm_question_shown(
            tg_user=tg_user,
            callback_token=q1.callback_token,
        )
        q1_correct_choice_id = await _get_correct_choice_id(conn, q1.item_id)
        await engine.submit_answer(
            tg_user=tg_user,
            selected_choice_id=q1_correct_choice_id,
            callback_token=q1.callback_token,
        )

        q2 = await engine.prepare_next_question(tg_user=tg_user)
        await engine.confirm_question_shown(
            tg_user=tg_user,
            callback_token=q2.callback_token,
        )
        q2_correct_choice_id = await _get_correct_choice_id(conn, q2.item_id)
        await engine.submit_answer(
            tg_user=tg_user,
            selected_choice_id=q2_correct_choice_id,
            callback_token=q2.callback_token,
        )

        finished = await engine.finish_attempt(
            tg_user=tg_user,
            completion_reason="question_limit_reached",
        )

        assert finished.status == "finished"
        assert finished.total_answers == 2
        assert finished.correct_answers == 2
        assert finished.completion_reason == "question_limit_reached"

        cursor = await conn.execute(
            "SELECT status, completion_reason FROM vocab_attempts WHERE id = ?",
            (finished.vocab_attempt_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["status"] == "finished"
        assert row["completion_reason"] == "question_limit_reached"

        cursor = await conn.execute(
            "SELECT status, completion_reason FROM mode_runs WHERE id = ?",
            (finished.mode_run_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["status"] == "finished"
        assert row["completion_reason"] == "question_limit_reached"

        user_row = await conn.execute(
            "SELECT id FROM users WHERE telegram_user_id = ?",
            (910304,),
        )
        user_db = await user_row.fetchone()
        assert user_db is not None

        fsm_repo = FsmRuntimeRepository(conn)
        state = await fsm_repo.get_state(ModeCode.VOCAB, int(user_db["id"]))
        assert state is None

        await close_container()

    asyncio.run(run())
