from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧠 Словарный запас", callback_data="vocab:intro")],
            [InlineKeyboardButton(text="🎓 Уровневый тест", callback_data="level:start")],
            [InlineKeyboardButton(text="🇵🇹 Экзамен A2 (CIPLE)", callback_data="ciple:start")],
        ]
    )


def _start_text() -> str:
    return (
        "Пройди короткий тест и узнай свой уровень португальского.\n\n"
        "Бот может:\n"
        "• оценить словарный запас\n"
        "• определить уровень CEFR\n"
        "• проверить готовность к экзамену A2 (CIPLE)"
    )


def build_start_router() -> Router:
    router = Router(name="start_common_router")

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        await message.answer(
            _start_text(),
            reply_markup=_start_keyboard(),
        )

    @router.callback_query(F.data == "menu:root")
    async def menu_root_handler(callback: CallbackQuery) -> None:
        if callback.message is not None:
            await callback.message.edit_text(
                _start_text(),
                reply_markup=_start_keyboard(),
            )
        await callback.answer()

    return router
