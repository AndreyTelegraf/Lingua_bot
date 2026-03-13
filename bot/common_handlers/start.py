from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧠 Словарный запас", callback_data="vocab:intro")],
            [InlineKeyboardButton(text="💪 Уровневый тест", callback_data="level:start")],
            [InlineKeyboardButton(text="🇵🇹 Экзамен A2 (CIPLE)", callback_data="ciple:start")],
        ]
    )


def _start_text() -> str:
    return (
        "Пройдите тесты и узнайте свой уровень португальского.\n\n"
        "ЯзыкоБот может:\n\n"
        "- оценить словарный запас – 3 минуты\n"
        "- определить уровень CEFR – 10 минут\n"
        "- проверить готовность к экзамену A2 (CIPLE) – 30+ минут\n\n"
        '*временно доступен только "Словарный запас".'
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

    @router.callback_query(F.data == "level:start")
    async def level_placeholder_handler(callback: CallbackQuery) -> None:
        await callback.answer("Уровневый тест скоро будет доступен", show_alert=True)

    @router.callback_query(F.data == "ciple:start")
    async def ciple_placeholder_handler(callback: CallbackQuery) -> None:
        await callback.answer("Экзамен A2 (CIPLE) скоро будет доступен", show_alert=True)

    return router
