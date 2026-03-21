from __future__ import annotations

import sqlite3

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import get_settings
from handlers.vocab_v2 import vocab_v2_callback as run_vocab_v2_callback
from handlers.vocab_v2 import vocab_v2_start as run_vocab_v2_start
from services.vocab_runtime.fsm_store import InMemoryVocabFSMStore

_STORE = InMemoryVocabFSMStore()


def _conn() -> sqlite3.Connection:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _keyboard(rows: list[dict[str, object]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=str(r["text"]), callback_data=str(r["callback_data"]))] for r in rows]
    )


def _extract_runtime_branch(payload: dict[str, object] | None) -> str:
    if not isinstance(payload, dict):
        return "legacy"
    raw = payload.get("runtime_branch", "legacy")
    return "cat" if str(raw) == "cat" else "legacy"


def _attach_ui_branch(payload: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {"runtime_branch": "legacy", "ui_branch": "legacy"}

    out = dict(payload)
    branch = _extract_runtime_branch(payload)
    out["runtime_branch"] = branch
    out["ui_branch"] = branch
    return out


def _decorate_text_for_branch(text: object, *, ui_branch: str) -> str:
    base = str(text)
    if ui_branch == "cat":
        return f"🎯 CAT\n\n{base}"
    return base


def _decorate_keyboard_for_branch(
    keyboard: object,
    *,
    ui_branch: str,
) -> object:
    if ui_branch != "cat":
        return keyboard

    if keyboard is None:
        return [
            {"text": "ℹ️ Adaptive mode", "callback_data": "vocab:cat:info"},
        ]

    if isinstance(keyboard, list):
        return [
            {"text": "ℹ️ Adaptive mode", "callback_data": "vocab:cat:info"},
            *keyboard,
        ]

    return keyboard


def _build_cat_visible_payload(out: dict[str, object]) -> dict[str, object]:
    base_text = str(out.get("text", ""))
    return {
        **out,
        "text": _decorate_text_for_branch(base_text, ui_branch="cat"),
        "keyboard": _decorate_keyboard_for_branch(out.get("keyboard"), ui_branch="cat"),
        "visible_mode": "cat",
        "visible_semantics": "adaptive",
    }


def _build_legacy_visible_payload(out: dict[str, object]) -> dict[str, object]:
    return {
        **out,
        "text": _decorate_text_for_branch(out.get("text", ""), ui_branch="legacy"),
        "keyboard": _decorate_keyboard_for_branch(out.get("keyboard"), ui_branch="legacy"),
        "visible_mode": "legacy",
        "visible_semantics": "static",
    }


def _attach_ui_render(payload: dict[str, object] | None) -> dict[str, object]:
    out = _attach_ui_branch(payload)
    branch = str(out.get("ui_branch", "legacy"))
    if branch == "cat":
        return _build_cat_visible_payload(out)
    return _build_legacy_visible_payload(out)


def run_vocab_v2_start_ui(*, conn, store, user_id: int) -> dict[str, object]:
    out = run_vocab_v2_start(conn=conn, store=store, user_id=user_id)
    return _attach_ui_render(out)


def run_vocab_v2_callback_ui(*, conn, store, user_id: int, callback_data: str) -> dict[str, object]:
    out = run_vocab_v2_callback(
        conn=conn,
        store=store,
        user_id=user_id,
        callback_data=callback_data,
    )
    return _attach_ui_render(out)



def _cat_info_payload() -> dict[str, object]:
    return {
        "ok": True,
        "text": "🎯 CAT\n\nЭтот тест сейчас работает в адаптивном режиме: следующие задания подбираются по вашим ответам.",
        "keyboard": [],
        "finished": False,
        "runtime_branch": "cat",
        "ui_branch": "cat",
        "visible_mode": "cat",
        "visible_semantics": "adaptive",
    }


def build_vocab_v2_router() -> Router:
    router = Router(name="vocab_v2_router")

    @router.message(Command("vocab2"))
    async def vocab2_start_handler(message: Message) -> None:
        if message.from_user is None:
            return

        conn = _conn()
        try:
            out = run_vocab_v2_start_ui(conn=conn, store=_STORE, user_id=int(message.from_user.id))
        finally:
            conn.close()

        await message.answer(
            str(out["text"]),
            reply_markup=_keyboard(out["keyboard"]) if out.get("keyboard") else None,
        )

    @router.callback_query(F.data == "vocab:cat:info")
    async def vocab2_cat_info_handler(callback: CallbackQuery) -> None:
        await callback.answer()

        if callback.message is None:
            return

        out = _cat_info_payload()
        await callback.message.answer(
            str(out["text"]),
            reply_markup=_keyboard(out["keyboard"]) if out.get("keyboard") else None,
        )

    @router.callback_query(F.data.startswith("vocab:pick:"))
    async def vocab2_callback_handler(callback: CallbackQuery) -> None:
        await callback.answer()

        if callback.from_user is None or callback.message is None or callback.data is None:
            return

        conn = _conn()
        try:
            out = run_vocab_v2_callback_ui(
                conn=conn,
                store=_STORE,
                user_id=int(callback.from_user.id),
                callback_data=str(callback.data),
            )
        finally:
            conn.close()

        if not out.get("ok", True):
            await callback.answer(str(out.get("text", "Session expired. Start again.")), show_alert=True)
            return

        await callback.message.edit_text(
            str(out["text"]),
            reply_markup=_keyboard(out["keyboard"]) if out.get("keyboard") else None,
        )

    return router
