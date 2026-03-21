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
        return {
            "ok": False,
            "text": "",
            "keyboard": [],
            "finished": True,
            "runtime_branch": "legacy",
            "ui_branch": "legacy",
            "visible_mode": "legacy",
            "visible_semantics": "static",
            "cat_payload_kind": None,
            "cat_native": False,
            "runtime_native_payload": None,
        }

    out = dict(payload)
    branch = _extract_runtime_branch(payload)
    out["runtime_branch"] = branch
    out["ui_branch"] = branch
    out.setdefault("visible_mode", "cat" if branch == "cat" else "legacy")
    out.setdefault("visible_semantics", "adaptive" if branch == "cat" else "static")
    out.setdefault("cat_payload_kind", None)
    out.setdefault("cat_native", False)
    out.setdefault("runtime_native_payload", None)
    return out


def _extract_cat_payload_kind(payload: dict[str, object] | None) -> str | None:
    if not isinstance(payload, dict):
        return None

    raw = payload.get("cat_payload_kind")
    if raw is not None:
        value = str(raw)
        if value in {"question", "result", "message"}:
            return value

    branch = _extract_runtime_branch(payload)
    if branch != "cat":
        return None

    if bool(payload.get("finished")):
        return "result"
    if payload.get("keyboard"):
        return "question"
    return "message"


def _extract_visible_mode(payload: dict[str, object] | None) -> str:
    if not isinstance(payload, dict):
        return "legacy"
    raw = str(payload.get("visible_mode", "legacy"))
    return "cat" if raw == "cat" else "legacy"


def _extract_visible_semantics(payload: dict[str, object] | None) -> str:
    if not isinstance(payload, dict):
        return "static"
    raw = str(payload.get("visible_semantics", "static"))
    return "adaptive" if raw == "adaptive" else "static"


def _extract_cat_native(payload: dict[str, object] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    return bool(payload.get("cat_native", False))


def _decorate_text_for_branch(text: object, *, ui_branch: str) -> str:
    base = str(text)
    if ui_branch == "cat":
        return f"🎯 CAT\n\n{base}"
    return base


def _build_cat_question_text(base_text: object) -> str:
    return f"🎯 Адаптивный вопрос\n\n{str(base_text)}\n\nСледующий вопрос подбирается по вашим ответам."


def _build_cat_result_text(base_text: object) -> str:
    return f"🎯 Адаптивный результат\n\n{str(base_text)}"


def _build_cat_message_text(base_text: object) -> str:
    return f"🎯 CAT\n\n{str(base_text)}"


def _decorate_keyboard_for_branch(
    keyboard: object,
    *,
    ui_branch: str,
) -> object:
    if ui_branch != "cat":
        return keyboard

    info_row = {"text": "ℹ️ Adaptive mode", "callback_data": "vocab:cat:info"}

    if keyboard is None:
        return [info_row]

    if isinstance(keyboard, list):
        if keyboard and isinstance(keyboard[0], dict) and keyboard[0].get("callback_data") == "vocab:cat:info":
            return keyboard
        return [info_row, *keyboard]

    return keyboard


def _render_cat_text_from_kind(base_text: object, *, kind: str | None) -> str:
    text = str(base_text)
    if kind == "question":
        return f"🎯 Адаптивный вопрос\n\n{text}\n\nСледующий вопрос подбирается по вашим ответам."
    if kind == "result":
        return f"🎯 Адаптивный результат\n\n{text}"
    return f"🎯 CAT\n\n{text}"


def _build_cat_visible_payload(out: dict[str, object]) -> dict[str, object]:
    kind = _extract_cat_payload_kind(out)
    return {
        **out,
        "text": _render_cat_text_from_kind(out.get("text", ""), kind=kind),
        "keyboard": _decorate_keyboard_for_branch(out.get("keyboard"), ui_branch="cat"),
        "runtime_branch": "cat",
        "ui_branch": "cat",
        "visible_mode": "cat",
        "visible_semantics": "adaptive",
        "cat_payload_kind": kind,
        "cat_native": True,
    }


def _build_legacy_visible_payload(out: dict[str, object]) -> dict[str, object]:
    return {
        **out,
        "text": _decorate_text_for_branch(out.get("text", ""), ui_branch="legacy"),
        "keyboard": _decorate_keyboard_for_branch(out.get("keyboard"), ui_branch="legacy"),
        "runtime_branch": "legacy",
        "ui_branch": "legacy",
        "visible_mode": "legacy",
        "visible_semantics": "static",
        "cat_payload_kind": None,
        "cat_native": False,
    }


def _runtime_native_payload(payload: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    raw = payload.get("runtime_native_payload")
    return raw if isinstance(raw, dict) else None


def _apply_runtime_native_payload(out: dict[str, object]) -> dict[str, object]:
    native = _runtime_native_payload(out)
    if native is None:
        return out

    rendered = dict(out)
    kind = str(native.get("kind") or "")
    prompt_text = native.get("prompt_text")
    stop_reason = native.get("stop_reason")

    rendered["cat_payload_kind"] = kind or rendered.get("cat_payload_kind")
    rendered["cat_native"] = True
    rendered["visible_mode"] = "cat"
    rendered["visible_semantics"] = "adaptive"

    if kind == "question":
        rendered["text"] = _build_cat_question_text(prompt_text or rendered.get("text", ""))
        rendered["keyboard"] = _decorate_keyboard_for_branch(rendered.get("keyboard"), ui_branch="cat")
    elif kind == "result":
        base = rendered.get("text", "")
        if stop_reason:
            base = f"{base}\n\nПричина остановки: {stop_reason}"
        rendered["text"] = _build_cat_result_text(base)
        rendered["keyboard"] = _decorate_keyboard_for_branch(rendered.get("keyboard"), ui_branch="cat")
    else:
        rendered["text"] = _build_cat_message_text(rendered.get("text", ""))
        rendered["keyboard"] = _decorate_keyboard_for_branch(rendered.get("keyboard"), ui_branch="cat")

    return rendered


def _attach_ui_render(payload: dict[str, object] | None) -> dict[str, object]:
    out = _attach_ui_branch(payload)
    branch = str(out.get("ui_branch", "legacy"))

    if branch == "cat":
        native = _runtime_native_payload(out)
        if native is not None:
            return _apply_runtime_native_payload(out)

        if bool(out.get("cat_native")):
            payload_kind = out.get("cat_payload_kind")
            rendered = dict(out)
            rendered["runtime_branch"] = "cat"
            rendered["ui_branch"] = "cat"
            rendered["visible_mode"] = "cat"
            rendered["visible_semantics"] = "adaptive"

            if payload_kind == "question":
                rendered["text"] = _build_cat_question_text(rendered.get("text", ""))
                rendered["keyboard"] = _decorate_keyboard_for_branch(rendered.get("keyboard"), ui_branch="cat")
            elif payload_kind == "result":
                rendered["text"] = _build_cat_result_text(rendered.get("text", ""))
                rendered["keyboard"] = _decorate_keyboard_for_branch(rendered.get("keyboard"), ui_branch="cat")
            else:
                rendered["text"] = _build_cat_message_text(rendered.get("text", ""))
                rendered["keyboard"] = _decorate_keyboard_for_branch(rendered.get("keyboard"), ui_branch="cat")
            return rendered

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
        "cat_payload_kind": "message",
        "cat_native": True,
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
