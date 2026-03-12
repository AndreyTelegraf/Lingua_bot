import asyncio
import sqlite3

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
        first_name="Answer",
        last_name="Pipeline",
        username=f"user_{user_id}",
        language_code="ru",
    )


def test_submit_answer_happy_path() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db

        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id = 910202")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id = 910202")
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910202)")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910202)")
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910202)")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id = 910202")
        await conn.execute("DELETE FROM mode_results WHERE user_id = 910202")
        await conn.execute("DELETE FROM mode_runs WHERE user_id = 910202")
        await conn.execute("DELETE FROM user_profiles WHERE user_id = 910202")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 910202")
        await conn.commit()

        engine = VocabEngine()
        tg_user = build_user(910202)

        await engine.start_attempt(
            tg_user=tg_user,
            prior_payload={"source": "answer_test"},
        )
        question = await engine.prepare_next_question(tg_user=tg_user)
        await engine.confirm_question_shown(
            tg_user=tg_user,
            callback_token=question.callback_token,
        )

        selected_choice_id = int(question.choices[0]["choice_id"])
        result = await engine.submit_answer(
            tg_user=tg_user,
            selected_choice_id=selected_choice_id,
            callback_token=question.callback_token,
        )

        assert result.item_id == question.item_id
        assert result.selected_choice_id == selected_choice_id
        assert result.next_status == "selecting"

        cursor = await conn.execute(
            """
            SELECT item_id, selected_choice_id, is_correct
            FROM vocab_answers
            WHERE attempt_id = ?
            """,
            (question.vocab_attempt_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert int(row["item_id"]) == question.item_id
        assert int(row["selected_choice_id"]) == selected_choice_id

        user_row = await conn.execute(
            "SELECT id FROM users WHERE telegram_user_id = ?",
            (910202,),
        )
        user_db = await user_row.fetchone()
        assert user_db is not None

        fsm_repo = FsmRuntimeRepository(conn)
        state = await fsm_repo.get_state(ModeCode.VOCAB, int(user_db["id"]))
        assert state is not None
        assert state.status.value == "selecting"
        assert state.expected_callback_token is None

        await engine.abort_attempt(
            tg_user=tg_user,
            completion_reason="answer_test_cleanup",
        )
        await close_container()

    asyncio.run(run())


def test_submit_answer_duplicate_token_rejected() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db

        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id = 910203")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id = 910203")
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910203)")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910203)")
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910203)")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id = 910203")
        await conn.execute("DELETE FROM mode_results WHERE user_id = 910203")
        await conn.execute("DELETE FROM mode_runs WHERE user_id = 910203")
        await conn.execute("DELETE FROM user_profiles WHERE user_id = 910203")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 910203")
        await conn.commit()

        engine = VocabEngine()
        tg_user = build_user(910203)

        await engine.start_attempt(
            tg_user=tg_user,
            prior_payload={"source": "duplicate_test"},
        )
        question = await engine.prepare_next_question(tg_user=tg_user)
        await engine.confirm_question_shown(
            tg_user=tg_user,
            callback_token=question.callback_token,
        )

        selected_choice_id = int(question.choices[0]["choice_id"])

        await engine.submit_answer(
            tg_user=tg_user,
            selected_choice_id=selected_choice_id,
            callback_token=question.callback_token,
        )

        try:
            await engine.submit_answer(
                tg_user=tg_user,
                selected_choice_id=selected_choice_id,
                callback_token=question.callback_token,
            )
        except RuntimeError as exc:
            assert str(exc).startswith("answer_not_expected:")
        else:
            raise AssertionError("duplicate answer was not rejected")

        await engine.abort_attempt(
            tg_user=tg_user,
            completion_reason="duplicate_test_cleanup",
        )
        await close_container()

    asyncio.run(run())
