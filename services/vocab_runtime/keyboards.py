from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def finished_keyboard(*, attempt_id: int | None = None) -> InlineKeyboardMarkup:
    review_cb = f"vocab_review:{int(attempt_id)}" if attempt_id is not None else "vocab_review"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Разбор ответов", callback_data=review_cb)],
            [InlineKeyboardButton(text="💪 Уровневый тест", callback_data="level:start")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="menu:root")],
            [InlineKeyboardButton(text="↺ Пройти ещё раз", callback_data="vocab:start")],
        ]
    )
