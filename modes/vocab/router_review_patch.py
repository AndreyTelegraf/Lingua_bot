from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.container import container
from services.vocab_runtime.review import render_review

router = Router()


async def _load_latest_attempt_answers(telegram_user_id: int) -> list[dict]:
    if container.db is None:
        raise RuntimeError("db_not_initialized")

    conn = container.db

    user_row = await (await conn.execute(
        """
        SELECT id
        FROM users
        WHERE telegram_user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (telegram_user_id,),
    )).fetchone()

    if user_row is None:
        return []

    attempt_row = await (await conn.execute(
        """
        SELECT id
        FROM vocab_attempts
        WHERE user_id = ?
          AND id IN (SELECT DISTINCT attempt_id FROM vocab_answers)
        ORDER BY id DESC
        LIMIT 1
        """,
        (int(user_row["id"]),),
    )).fetchone()

    if attempt_row is None:
        return []

    cursor = await conn.execute(
        """
        SELECT
            va.id AS answer_id,
            vi.lemma AS word,
            vi.correct_answer AS correct_answer,
            vc.choice_text AS selected_choice_text,
            va.is_correct AS is_correct,
            va.answer_kind AS answer_kind
        FROM vocab_answers va
        LEFT JOIN vocab_items vi ON vi.id = va.item_id
        LEFT JOIN vocab_choices vc ON vc.id = va.selected_choice_id
        WHERE va.attempt_id = ?
        ORDER BY va.id ASC
        """,
        (int(attempt_row["id"]),),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.callback_query(F.data == "vocab_review")
async def vocab_review(cb: CallbackQuery):
    answers = await _load_latest_attempt_answers(int(cb.from_user.id))

    if not answers:
        text = "Разбор ответов пока недоступен."
    else:
        text = render_review(answers)

    if cb.message is not None:
        await cb.message.answer(text)

    await cb.answer()
