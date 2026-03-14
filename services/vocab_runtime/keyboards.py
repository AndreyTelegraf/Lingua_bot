from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def finished_keyboard(
    *,
    attempt_id: int | None = None,
    share_text: str | None = None,
) -> InlineKeyboardMarkup:
    review_cb = f"vocab_review:{int(attempt_id)}" if attempt_id is not None else "vocab_review"
    rows = [
        [InlineKeyboardButton(text="📊 Разбор ответов", callback_data=review_cb)],
    ]
    if share_text:
        rows.append([InlineKeyboardButton(text="📤 Поделиться результатом", switch_inline_query=share_text)])
    rows.append([InlineKeyboardButton(text="🏠 В меню", callback_data="menu:root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
