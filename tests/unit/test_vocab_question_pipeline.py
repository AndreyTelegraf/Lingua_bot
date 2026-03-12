import asyncio
import json

from aiogram.types import User

from app.container import close_container, init_container, container
from domain.attempts.repository import FsmRuntimeRepository
from domain.shared.enums import ModeCode
from modes.vocab.engine import VocabEngine


def build_user(user_id: int) -> User:
    return User(
        id=user_id,
        is_bot=False,
        first_name="Question",
        last_name="Pipeline",
        username=f"user_{user_id}",
        language_code="ru",
    )


def test_prepare_next_question_smoke() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db

        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id = 910101")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id = 910101")
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910101)")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910101)")
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910101)")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id = 910101")
        await conn.execute("DELETE FROM mode_results WHERE user_id = 910101")
        await conn.execute("DELETE FROM mode_runs WHERE user_id = 910101")
        await conn.execute("DELETE FROM user_profiles WHERE user_id = 910101")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 910101")
        await conn.commit()

        engine = VocabEngine()
        tg_user = build_user(910101)

        started = await engine.start_attempt(
            tg_user=tg_user,
            prior_payload={"source": "question_test"},
        )
        assert started.status == "selecting"

        question = await engine.prepare_next_question(tg_user=tg_user)
        await engine.confirm_question_shown(
            tg_user=tg_user,
            callback_token=question.callback_token,
        )
        assert question.step_index == 1
        assert question.item_id > 0
        assert len(question.choices) >= 2

        cursor = await conn.execute(
            "SELECT selector_payload_json FROM vocab_selector_state WHERE attempt_id = ?",
            (question.vocab_attempt_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        payload = json.loads(row["selector_payload_json"])
        assert int(payload["current_question"]["item_id"]) == question.item_id
        assert int(payload["step_index"]) == 1

        cursor = await conn.execute(
            "SELECT current_step FROM vocab_attempts WHERE id = ?",
            (question.vocab_attempt_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert int(row["current_step"]) == 1

        user_row = await conn.execute(
            "SELECT id FROM users WHERE telegram_user_id = ?",
            (910101,),
        )
        user_db = await user_row.fetchone()
        assert user_db is not None

        fsm_repo = FsmRuntimeRepository(conn)
        state = await fsm_repo.get_state(ModeCode.VOCAB, int(user_db["id"]))
        assert state is not None
        assert state.status.value == "awaiting_answer"
        assert state.current_step == 1
        assert state.current_item_id is not None
        assert state.expected_callback_token is not None

        await engine.abort_attempt(
            tg_user=tg_user,
            completion_reason="question_test_cleanup",
        )
        await close_container()

    asyncio.run(run())
