from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.container import close_container, container, init_container
from modes.vocab.engine import VocabEngine


def _tg_user(uid: int):
    return SimpleNamespace(
        id=uid,
        username=f"u{uid}",
        first_name="Test",
        last_name="User",
        language_code="en",
        is_bot=False,
    )


async def _get_correct_choice_id(conn, item_id: int) -> int:
    cursor = await conn.execute(
        """
        SELECT id
        FROM vocab_choices
        WHERE item_id = ?
          AND is_correct = 1
        ORDER BY id ASC
        LIMIT 1
        """,
        (item_id,),
    )
    row = await cursor.fetchone()
    assert row is not None
    return int(row["id"])


def test_selector_excludes_last_attempt_items_when_pool_allows() -> None:
    async def run() -> None:
        await init_container()
        assert container.db is not None
        conn = container.db

        uid = 911401

        await conn.execute("DELETE FROM fsm_runtime_state WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = ?)", (uid,))
        await conn.execute("DELETE FROM vocab_selector_state WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = ?))", (uid,))
        await conn.execute("DELETE FROM vocab_attempt_events WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = ?)", (uid,))
        await conn.execute("DELETE FROM vocab_answers WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = ?))", (uid,))
        await conn.execute("DELETE FROM vocab_result_snapshots WHERE attempt_id IN (SELECT id FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = ?))", (uid,))
        await conn.execute("DELETE FROM vocab_attempts WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = ?)", (uid,))
        await conn.execute("DELETE FROM mode_results WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = ?)", (uid,))
        await conn.execute("DELETE FROM mode_runs WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = ?)", (uid,))
        await conn.execute("DELETE FROM user_mode_priors WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = ?)", (uid,))
        await conn.execute("DELETE FROM user_assessment_profile WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = ?)", (uid,))
        await conn.execute("DELETE FROM user_profiles WHERE user_id IN (SELECT id FROM users WHERE telegram_user_id = ?)", (uid,))
        await conn.execute("DELETE FROM users WHERE telegram_user_id = ?", (uid,))
        await conn.commit()

        engine = VocabEngine()
        tg_user = _tg_user(uid)

        started1 = await engine.start_attempt(tg_user=tg_user, prior_payload={"source": "recent_attempt_exclusion_test_1"})
        await conn.execute("UPDATE vocab_attempts SET question_limit = 2 WHERE id = ?", (started1.vocab_attempt_id,))
        await conn.commit()

        first_items: list[int] = []

        q1 = await engine.prepare_next_question(tg_user=tg_user)
        first_items.append(int(q1.item_id))
        await engine.confirm_question_shown(tg_user=tg_user, callback_token=q1.callback_token)
        c1 = await _get_correct_choice_id(conn, q1.item_id)
        await engine.submit_answer(tg_user=tg_user, selected_choice_id=c1, callback_token=q1.callback_token)

        q2 = await engine.prepare_next_question(tg_user=tg_user)
        first_items.append(int(q2.item_id))
        await engine.confirm_question_shown(tg_user=tg_user, callback_token=q2.callback_token)
        c2 = await _get_correct_choice_id(conn, q2.item_id)
        await engine.submit_answer(tg_user=tg_user, selected_choice_id=c2, callback_token=q2.callback_token)

        await engine.finish_attempt(tg_user=tg_user, completion_reason="question_limit_reached")

        started2 = await engine.start_attempt(tg_user=tg_user, prior_payload={"source": "recent_attempt_exclusion_test_2"})
        await conn.execute("UPDATE vocab_attempts SET question_limit = 2 WHERE id = ?", (started2.vocab_attempt_id,))
        await conn.commit()

        q3 = await engine.prepare_next_question(tg_user=tg_user)
        assert int(q3.item_id) not in first_items
        await engine.confirm_question_shown(tg_user=tg_user, callback_token=q3.callback_token)
        c3 = await _get_correct_choice_id(conn, q3.item_id)
        await engine.submit_answer(tg_user=tg_user, selected_choice_id=c3, callback_token=q3.callback_token)

        q4 = await engine.prepare_next_question(tg_user=tg_user)
        assert int(q4.item_id) not in first_items

        await close_container()

    asyncio.run(run())
