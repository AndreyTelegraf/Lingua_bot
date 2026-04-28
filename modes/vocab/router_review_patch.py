from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.container import container
from services.vocab_runtime.review import render_review
from bot.common_handlers.start import set_last_review_message_id


async def _load_attempt_answers_by_attempt_id(*, telegram_user_id: int, attempt_id: int) -> list[dict]:
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
        WHERE id = ?
          AND user_id = ?
          AND id IN (SELECT DISTINCT attempt_id FROM vocab_answers)
        LIMIT 1
        """,
        (attempt_id, int(user_row["id"])),
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
        LEFT JOIN vocab_items_runtime_v3 vi ON vi.id = va.item_id
        LEFT JOIN vocab_choices_v3 vc ON vc.id = va.selected_choice_id
        WHERE va.attempt_id = ?
        ORDER BY va.id ASC
        """,
        (int(attempt_row["id"]),),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


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

    return await _load_attempt_answers_by_attempt_id(
        telegram_user_id=telegram_user_id,
        attempt_id=int(attempt_row["id"]),
    )


def build_vocab_review_router() -> Router:
    router = Router(name="vocab_review")

    @router.callback_query(F.data == "vocab_review")
    async def vocab_review_latest(cb: CallbackQuery):
        answers = await _load_latest_attempt_answers(int(cb.from_user.id))
        text = "Разбор ответов пока недоступен." if not answers else render_review(answers)
        if cb.message is not None:
            sent = await cb.message.answer(text)
        if cb.from_user:
            set_last_review_message_id(cb.from_user.id, sent.message_id)
        await cb.answer()

    @router.callback_query(F.data.startswith("vocab_review:"))
    async def vocab_review_attempt(cb: CallbackQuery):
        raw = str(cb.data or "")
        try:
            attempt_id = int(raw.split(":", 1)[1])
        except Exception:
            attempt_id = 0

        answers = []
        if attempt_id > 0:
            answers = await _load_attempt_answers_by_attempt_id(
                telegram_user_id=int(cb.from_user.id),
                attempt_id=attempt_id,
            )

        text = "Разбор ответов пока недоступен." if not answers else render_review(answers)
        if cb.message is not None:
            sent = await cb.message.answer(text)
        if cb.from_user:
            set_last_review_message_id(cb.from_user.id, sent.message_id)
        await cb.answer()

    return router
