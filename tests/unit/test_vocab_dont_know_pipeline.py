import asyncio

from aiogram.types import User

from app.container import close_container, init_container, container
from domain.attempts.repository import FsmRuntimeRepository
from domain.shared.enums import ModeCode
from modes.vocab.engine import VocabEngine


def build_user(user_id: int) -> User:
    return User(
        id=user_id,
        is_bot=False,
        first_name="Dont",
        last_name="Know",
        username=f"user_{user_id}",
        language_code="ru",
    )


def test_submit_dont_know_happy_path() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db

        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id = 910701")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id = 910701")
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910701)")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910701)")
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910701)")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id = 910701")
        await conn.execute("DELETE FROM mode_results WHERE user_id = 910701")
        await conn.execute("DELETE FROM mode_runs WHERE user_id = 910701")
        await conn.execute("DELETE FROM user_profiles WHERE user_id = 910701")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 910701")
        await conn.commit()

        engine = VocabEngine()
        tg_user = build_user(910701)

        await engine.start_attempt(
            tg_user=tg_user,
            prior_payload={"source": "dont_know_test"},
        )
        question = await engine.prepare_next_question(tg_user=tg_user)
        await engine.confirm_question_shown(
            tg_user=tg_user,
            callback_token=question.callback_token,
        )

        result = await engine.submit_dont_know(
            tg_user=tg_user,
            callback_token=question.callback_token,
        )

        assert result.item_id == question.item_id
        assert result.answer_kind == "dont_know"
        assert result.next_status == "selecting"

        cursor = await conn.execute(
            """
            SELECT item_id, selected_choice_id, is_correct, answer_status, answer_kind
            FROM vocab_answers
            WHERE attempt_id = ?
            """,
            (question.vocab_attempt_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert int(row["item_id"]) == question.item_id
        assert row["selected_choice_id"] is None
        assert int(row["is_correct"]) == 0
        assert row["answer_status"] == "dont_know"
        assert row["answer_kind"] == "dont_know"

        cursor = await conn.execute(
            """
            SELECT questions_answered, correct_count, dont_know_count
            FROM vocab_attempts
            WHERE id = ?
            """,
            (question.vocab_attempt_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert int(row["questions_answered"]) == 1
        assert int(row["correct_count"]) == 0
        assert int(row["dont_know_count"]) == 1

        cursor = await conn.execute(
            """
            SELECT event_type, reason_code
            FROM vocab_attempt_events
            WHERE attempt_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (question.vocab_attempt_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["event_type"] == "dont_know_selected"
        assert row["reason_code"] == "dont_know"

        user_row = await conn.execute(
            "SELECT id FROM users WHERE telegram_user_id = ?",
            (910701,),
        )
        user_db = await user_row.fetchone()
        assert user_db is not None

        fsm_repo = FsmRuntimeRepository(conn)
        state = await fsm_repo.get_state(ModeCode.VOCAB, int(user_db["id"]))
        assert state is not None
        assert state.status.value == "selecting"

        await engine.abort_attempt(
            tg_user=tg_user,
            completion_reason="dont_know_test_cleanup",
        )
        await close_container()

    asyncio.run(run())


def test_submit_dont_know_duplicate_token_rejected() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db

        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id = 910702")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id = 910702")
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910702)")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910702)")
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910702)")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id = 910702")
        await conn.execute("DELETE FROM mode_results WHERE user_id = 910702")
        await conn.execute("DELETE FROM mode_runs WHERE user_id = 910702")
        await conn.execute("DELETE FROM user_profiles WHERE user_id = 910702")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 910702")
        await conn.commit()

        engine = VocabEngine()
        tg_user = build_user(910702)

        await engine.start_attempt(
            tg_user=tg_user,
            prior_payload={"source": "dont_know_duplicate_test"},
        )
        question = await engine.prepare_next_question(tg_user=tg_user)
        await engine.confirm_question_shown(
            tg_user=tg_user,
            callback_token=question.callback_token,
        )

        await engine.submit_dont_know(
            tg_user=tg_user,
            callback_token=question.callback_token,
        )

        try:
            await engine.submit_dont_know(
                tg_user=tg_user,
                callback_token=question.callback_token,
            )
        except RuntimeError as exc:
            assert str(exc).startswith("dont_know_not_expected:")
        else:
            raise AssertionError("duplicate dont_know was not rejected")

        await engine.abort_attempt(
            tg_user=tg_user,
            completion_reason="dont_know_duplicate_cleanup",
        )
        await close_container()

    asyncio.run(run())
