from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧠 Vocabulary Test", callback_data="vocab:intro")],
        ]
    )


def build_start_router() -> Router:
    router = Router(name="start_common_router")

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        await message.answer(
            "ЯзыкоБот\n\nВыберите режим тестирования.",
            reply_markup=_start_keyboard(),
        )

    return router
