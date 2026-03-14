from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, InputTextMessageContent


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Словарный запас", callback_data="vocab:intro")],
            [InlineKeyboardButton(text="🧠 Уровневый тест", callback_data="level:start")],
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


def _share_vocab_range_from_code(range_code: str) -> str:
    code = str(range_code or "").strip()
    mapping = {
        "1500": "до 1500",
        "2500": "1500–2500",
        "4000": "2500–4000",
        "6000": "4000–6000",
        "8000": "6000–8000",
    }
    return mapping.get(code, code)


def _build_inline_share_message(range_code: str) -> str:
    vocab_range = _share_vocab_range_from_code(range_code)
    return (
        f"🇵🇹 ЯзыкоБот оценил мой словарный запас португальского в *{vocab_range} слов*.\n\n"
        "А сколько знаете вы?\n\n"
        f"Проверьте себя через [ЯзыкоБот](https://t.me/lin_gua_bot?start=sv_{range_code})"
    )


def _parse_share_start_arg(command: CommandObject | None) -> tuple[str | None, str | None]:
    if command is None or not command.args:
        return None, None

    raw = str(command.args).strip()
    if raw.startswith("sv_"):
        return "share_vocab", raw.removeprefix("sv_")
    return None, None


def build_start_router() -> Router:
    router = Router(name="start_common_router")

    @router.message(CommandStart())
    async def start_handler(message: Message, command: CommandObject | None = None) -> None:
        _source, _range_code = _parse_share_start_arg(command)

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

    @router.inline_query()
    async def inline_share_handler(inline_query: InlineQuery) -> None:
        raw = str(inline_query.query or "").strip()
        if not raw.startswith("sv_"):
            await inline_query.answer([], cache_time=1, is_personal=True)
            return

        range_code = raw.removeprefix("sv_")
        message_text = _build_inline_share_message(range_code)

        article = InlineQueryResultArticle(
            id=f"share_vocab_{range_code}",
            title="📤 Поделиться результатом",
            description=f"Поделиться результатом словарного теста: {_share_vocab_range_from_code(range_code)} слов",
            input_message_content=InputTextMessageContent(
                message_text=message_text,
                parse_mode="Markdown",
                disable_web_page_preview=False,
            ),
        )
        await inline_query.answer([article], cache_time=1, is_personal=True)

    @router.callback_query(F.data == "level:start")
    async def level_placeholder_handler(callback: CallbackQuery) -> None:
        await callback.answer("🧠 Уровневый тест скоро будет доступен", show_alert=True)

    @router.callback_query(F.data == "ciple:start")
    async def ciple_placeholder_handler(callback: CallbackQuery) -> None:
        await callback.answer("Экзамен A2 (CIPLE) скоро будет доступен", show_alert=True)

    return router
