from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def finished_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Разбор ответов", callback_data="vocab_review")]
        ]
    )
