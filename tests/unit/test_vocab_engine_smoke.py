import asyncio

from aiogram.types import User

from app.container import close_container, init_container, container
from modes.vocab.engine import VocabEngine


def build_user(user_id: int) -> User:
    return User(
        id=user_id,
        is_bot=False,
        first_name="Andrey",
        last_name="Telegraf",
        username=f"user_{user_id}",
        language_code="ru",
    )


def test_vocab_start_abort_smoke() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db

        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id = 910001")
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id = 910001")
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910001)")
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910001)")
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id = 910001)")
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id = 910001")
        await conn.execute("DELETE FROM attempt_events WHERE user_id = 910001")
        await conn.execute("DELETE FROM mode_results WHERE user_id = 910001")
        await conn.execute("DELETE FROM mode_runs WHERE user_id = 910001")
        await conn.execute("DELETE FROM user_mode_priors WHERE user_id = 910001")
        await conn.execute("DELETE FROM user_assessment_profile WHERE user_id = 910001")
        await conn.execute("DELETE FROM user_profiles WHERE user_id = 910001")
        await conn.execute("DELETE FROM users WHERE telegram_user_id = 910001")
        await conn.commit()

        engine = VocabEngine()
        tg_user = build_user(910001)

        started = await engine.start_attempt(
            tg_user=tg_user,
            prior_payload={"source": "unit_test"},
        )
        assert started.status == "selecting"

        aborted = await engine.abort_attempt(
            tg_user=tg_user,
            completion_reason="unit_test_abort",
        )
        assert aborted.status == "aborted"

        cursor = await conn.execute(
            "SELECT status, completion_reason FROM vocab_attempts WHERE id = ?",
            (aborted.vocab_attempt_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["status"] == "aborted"
        assert row["completion_reason"] == "unit_test_abort"

        cursor = await conn.execute(
            "SELECT status, completion_reason FROM mode_runs WHERE id = ?",
            (aborted.mode_run_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["status"] == "aborted"
        assert row["completion_reason"] == "unit_test_abort"

        cursor = await conn.execute(
            "SELECT COUNT(*) AS n FROM vocab_attempt_events WHERE attempt_id = ?",
            (aborted.vocab_attempt_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert int(row["n"]) >= 2

        cursor = await conn.execute(
            "SELECT COUNT(*) AS n FROM fsm_runtime_state WHERE mode = 'vocab' AND user_id = (SELECT id FROM users WHERE telegram_user_id = 910001)",
        )
        row = await cursor.fetchone()
        assert row is not None
        assert int(row["n"]) == 0

        await close_container()

    asyncio.run(run())
