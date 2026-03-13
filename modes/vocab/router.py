from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.container import container
from modes.vocab.engine import VocabEngine
from modes.vocab.repo import VocabRepository


def _progress_bar(current: int, total: int, *, width: int = 14) -> str:
    if total <= 0:
        total = 1
    if current < 0:
        current = 0
    if current > total:
        current = total

    filled = round((current / total) * width)
    if filled < 0:
        filled = 0
    if filled > width:
        filled = width
    return ("█" * filled) + ("░" * (width - filled))


def _intro_text() -> str:
    return (
        "Этот тест оценивает ваш пассивный словарный запас португальского языка.\n\n"
        "Вам будет показаны португальские слова.\n"
        "Нужно будет выбрать правильный перевод.\n\n"
        "24 задания с вариантами ответов.\n"
        "Тест займёт примерно 3 минуты."
    )


def _intro_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➝ Начать тест", callback_data="vocab:start")],
            [InlineKeyboardButton(text="← Назад", callback_data="menu:root")],
        ]
    )


def _question_keyboard(question_choices: list[dict[str, object]], callback_token: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    rows.append(
        [
            InlineKeyboardButton(
                text="❗️ Не знаю",
                callback_data=f"vocab:dontknow:{callback_token}",
            )
        ]
    )

    for choice in question_choices:
        choice_id = int(choice["choice_id"])
        choice_text = str(choice["choice_text"])
        rows.append(
            [
                InlineKeyboardButton(
                    text=choice_text,
                    callback_data=f"vocab:answer:{choice_id}:{callback_token}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="⚠️ Сообщить об ошибке",
                callback_data=f"vocab:report:{callback_token}",
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _result_text(
    *,
    estimated_vocab_band: str,
    estimated_vocab_size: int,
    confidence: float,
) -> str:
    return (
        f"Ваш пассивный словарный запас составляет около {estimated_vocab_size} слов.\n\n"
        "Это приблизительная оценка, она основана на частотности слов и ваших ответах."
    )


def _result_keyboard(*, attempt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Разбор ответов", callback_data=f"vocab_review:{int(attempt_id)}")],
            [InlineKeyboardButton(text="🎓 Уровневый тест", callback_data="level:start")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="menu:root")],
            [InlineKeyboardButton(text="↺ Пройти ещё раз", callback_data="vocab:start")],
        ]
    )


async def _get_active_attempt_stats(*, tg_user) -> tuple[int, int] | None:
    if container.db is None:
        raise RuntimeError("db_not_initialized")

    repo = VocabRepository(container.db)
    user_id = await repo.upsert_user_from_telegram(tg_user)
    active = await repo.get_active_vocab_attempt(user_id=user_id)
    if active is None:
        return None

    attempt_stats = await repo.get_attempt_stats(attempt_id=int(active["id"]))
    if attempt_stats is None:
        raise RuntimeError("attempt_stats_not_found")

    answer_stats = await repo.get_attempt_answer_stats(attempt_id=int(active["id"]))
    question_limit = int(attempt_stats["question_limit"])
    total_answers = int(answer_stats["total_answers"])
    return question_limit, total_answers


async def _render_question(callback: CallbackQuery, engine: VocabEngine, question) -> None:
    if callback.message is None:
        return

    progress = _progress_bar(int(question.step_index), int(question.question_limit))
    text = (
        f"{progress} {int(question.step_index)} / {int(question.question_limit)}\n\n"
        f"Переведите на русский:\n\n"
        f"{str(question.question_text)}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=_question_keyboard(question.choices, question.callback_token),
    )

    await engine.confirm_question_shown(
        tg_user=callback.from_user,
        callback_token=question.callback_token,
        message_id=callback.message.message_id,
    )


async def _render_finish(callback: CallbackQuery, engine: VocabEngine, reason: str) -> None:
    if callback.message is None:
        return

    finished = await engine.finish_attempt(
        tg_user=callback.from_user,
        completion_reason=reason,
    )

    await callback.message.edit_text(
        _result_text(
            estimated_vocab_band=finished.estimated_vocab_band,
            estimated_vocab_size=finished.estimated_vocab_size,
            confidence=finished.confidence,
        ),
        reply_markup=_result_keyboard(attempt_id=int(finished.vocab_attempt_id)),
    )


async def _render_next_or_finish(callback: CallbackQuery, engine: VocabEngine) -> None:
    max_prepare_attempts = 5
    attempt_no = 0

    while attempt_no < max_prepare_attempts:
        stats = await _get_active_attempt_stats(tg_user=callback.from_user)
        if stats is None:
            if callback.message is not None:
                await callback.message.edit_text(
                    _intro_text(),
                    reply_markup=_intro_keyboard(),
                )
            return

        question_limit, total_answers = stats
        if total_answers >= question_limit:
            await _render_finish(callback, engine, "question_limit_reached")
            return

        try:
            question = await engine.prepare_next_question(tg_user=callback.from_user)
        except RuntimeError as exc:
            if str(exc) == "no_vocab_items_available":
                try:
                    await _render_finish(callback, engine, "stop_rule_exhausted_items")
                except RuntimeError as finish_exc:
                    if str(finish_exc) != "finish_not_allowed_items_remaining":
                        raise
                    try:
                        await engine.abort_attempt(
                            tg_user=callback.from_user,
                            completion_reason="bank_exhausted_after_report",
                        )
                    except RuntimeError:
                        pass

                    if callback.message is not None:
                        await callback.message.edit_text(
                            (
                                "Доступные вопросы закончились раньше завершения теста.\n\n"
                                "Можно начать попытку заново."
                            ),
                            reply_markup=_result_keyboard(attempt_id=int(finished.vocab_attempt_id)),
                        )
                return
            raise

        try:
            await _render_question(callback, engine, question)
            return
        except Exception:
            try:
                await engine.reject_prepared_question(
                    tg_user=callback.from_user,
                    callback_token=question.callback_token,
                    reason_code="telegram_render_failed",
                )
            except RuntimeError:
                pass
            attempt_no += 1

    try:
        await engine.abort_attempt(
            tg_user=callback.from_user,
            completion_reason="render_retry_exhausted",
        )
    except RuntimeError:
        pass

    if callback.message is not None:
        await callback.message.edit_text(
            "Техническая ошибка при показе задания. Попробуйте начать тест заново.",
            reply_markup=_result_keyboard(attempt_id=int(finished.vocab_attempt_id)),
        )


def build_vocab_router() -> Router:
    router = Router(name="vocab_router")

    @router.callback_query(F.data == "vocab:intro")
    async def vocab_intro_cb(callback: CallbackQuery) -> None:
        await callback.answer()
        if callback.message is None:
            return

        await callback.message.edit_text(
            _intro_text(),
            reply_markup=_intro_keyboard(),
        )

    @router.callback_query(F.data == "vocab:start")
    async def vocab_start_cb(callback: CallbackQuery) -> None:
        await callback.answer()
        if callback.message is None:
            return

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        loading_msg = None
        try:
            loading_msg = await callback.message.answer("Подбираем следующий вопрос...")
        except Exception:
            loading_msg = None

        engine = VocabEngine()

        try:
            try:
                await engine.abort_attempt(
                    tg_user=callback.from_user,
                    completion_reason="restart_before_new_attempt",
                )
            except RuntimeError:
                pass

            await engine.start_attempt(
                tg_user=callback.from_user,
                prior_payload={"source": "telegram_ui"},
            )
            await _render_next_or_finish(callback, engine)
        finally:
            if loading_msg is not None:
                try:
                    await loading_msg.delete()
                except Exception:
                    pass

    @router.callback_query(F.data.startswith("vocab:answer:"))
    async def vocab_answer_cb(callback: CallbackQuery) -> None:
        await callback.answer()
        if callback.message is None:
            return

        parts = callback.data.split(":", 3)
        if len(parts) != 4:
            await callback.message.answer("Некорректный ответ.")
            return

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        loading_msg = None
        try:
            loading_msg = await callback.message.answer("Подбираем следующий вопрос...")
        except Exception:
            loading_msg = None

        _, _, choice_id_raw, callback_token = parts
        choice_id = int(choice_id_raw)

        engine = VocabEngine()
        try:
            await engine.submit_answer(
                tg_user=callback.from_user,
                selected_choice_id=choice_id,
                callback_token=callback_token,
            )
            await _render_next_or_finish(callback, engine)
        except RuntimeError as e:
            msg = str(e)
            if msg.startswith("answer_not_expected:") or msg == "stale_callback_token":
                try:
                    await callback.answer("Этот ответ уже обработан.", show_alert=False)
                except Exception:
                    pass
                return
            raise
        finally:
            if loading_msg is not None:
                try:
                    await loading_msg.delete()
                except Exception:
                    pass

    @router.callback_query(F.data.startswith("vocab:dontknow:"))
    async def vocab_dont_know_cb(callback: CallbackQuery) -> None:
        await callback.answer()
        if callback.message is None:
            return

        parts = callback.data.split(":", 2)
        if len(parts) != 3:
            await callback.message.answer("Некорректный callback.")
            return

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        loading_msg = None
        try:
            loading_msg = await callback.message.answer("Подбираем следующий вопрос...")
        except Exception:
            loading_msg = None

        _, _, callback_token = parts

        engine = VocabEngine()
        try:
            await engine.submit_dont_know(
                tg_user=callback.from_user,
                callback_token=callback_token,
            )
            await _render_next_or_finish(callback, engine)
        except RuntimeError as e:
            msg = str(e)
            if msg.startswith("answer_not_expected:") or msg == "stale_callback_token":
                try:
                    await callback.answer("Уже обработано.", show_alert=False)
                except Exception:
                    pass
                return
            raise
        finally:
            if loading_msg is not None:
                try:
                    await loading_msg.delete()
                except Exception:
                    pass

    @router.callback_query(F.data.startswith("vocab:report:"))
    async def vocab_report_cb(callback: CallbackQuery) -> None:
        await callback.answer("Сообщение об ошибке записано.", show_alert=False)
        if callback.message is None:
            return

        parts = callback.data.split(":", 2)
        if len(parts) != 3:
            await callback.message.answer("Некорректный callback.")
            return

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        loading_msg = None
        try:
            loading_msg = await callback.message.answer("Подбираем следующий вопрос...")
        except Exception:
            loading_msg = None

        _, _, callback_token = parts

        engine = VocabEngine()
        try:
            await engine.submit_report_error(
                tg_user=callback.from_user,
                callback_token=callback_token,
            )
            await _render_next_or_finish(callback, engine)
        except RuntimeError as e:
            msg = str(e)
            if msg.startswith("report_error_not_expected:") or msg == "stale_callback_token":
                try:
                    await callback.answer("Уже обработано.", show_alert=False)
                except Exception:
                    pass
                return
            raise
        finally:
            if loading_msg is not None:
                try:
                    await loading_msg.delete()
                except Exception:
                    pass

    @router.message(F.text == "/vocab")
    async def vocab_command(message: Message) -> None:
        await message.answer(
            _intro_text(),
            reply_markup=_intro_keyboard(),
        )

    return router
