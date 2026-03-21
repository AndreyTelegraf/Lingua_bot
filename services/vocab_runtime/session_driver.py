from __future__ import annotations

import sqlite3

from services.vocab_runtime.aiogram_glue import handle_callback, handle_start
from services.vocab_runtime.presenter import present_finished, present_question
from services.vocab_runtime.keyboards import finished_keyboard


def _cat_passthrough_fields(view: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(view, dict):
        return {}

    out: dict[str, object] = {}
    for key in (
        "cat_route",
        "runtime_branch",
        "runtime_native_payload",
        "cat_native",
        "visible_mode",
        "visible_semantics",
        "cat_payload_kind",
        "e2e_runtime_native",
        "e2e_payload_kind",
    ):
        if key in view:
            out[key] = view[key]

    if "cat_route" in view and "runtime_branch" not in out:
        out["runtime_branch"] = "cat"
    if "cat_route" in view and "cat_native" not in out:
        out["cat_native"] = True
    if "cat_route" in view and "visible_mode" not in out:
        out["visible_mode"] = "cat"
    if "cat_route" in view and "visible_semantics" not in out:
        out["visible_semantics"] = "adaptive"

    return out


def start_session_view(conn: sqlite3.Connection, *, user_id: int) -> dict[str, object]:
    out = handle_start(conn, user_id=user_id)
    view = out["view"]

    if view is None:
        return {
            "fsm": out["fsm"],
            "text": "No questions available.",
            "keyboard": [],
            **_cat_passthrough_fields(view),
        }

    if "status" in view and view["status"] == "finished":
        return {
            "fsm": out["fsm"],
            "text": present_finished(view),
            "keyboard": finished_keyboard(
                attempt_id=int(view.get("attempt_id")) if view.get("attempt_id") is not None else None
            ),
            "finished": True,
            **_cat_passthrough_fields(view),
        }

    return {
        "fsm": out["fsm"],
        "text": present_question(view),
        "keyboard": view["keyboard"],
        **_cat_passthrough_fields(view),
    }


def answer_session_view(
    conn: sqlite3.Connection,
    *,
    fsm: object,
    callback_data: str,
) -> dict[str, object]:
    out = handle_callback(conn, fsm=fsm, callback_data=callback_data)
    next_view = out["next_view"]

    if next_view is None:
        return {
            "fsm": out["fsm"],
            "answer_result": out["answer_result"],
            "text": "No next question.",
            "keyboard": [],
            **_cat_passthrough_fields(next_view),
        }

    if "status" in next_view and next_view["status"] == "finished":
        return {
            "fsm": out["fsm"],
            "answer_result": out["answer_result"],
            "text": present_finished(next_view),
            "keyboard": finished_keyboard(
                attempt_id=int(next_view.get("attempt_id")) if next_view.get("attempt_id") is not None else None
            ),
            "finished": True,
            **_cat_passthrough_fields(next_view),
        }

    return {
        "fsm": out["fsm"],
        "answer_result": out["answer_result"],
        "text": present_question(next_view),
        "keyboard": next_view["keyboard"],
        **_cat_passthrough_fields(next_view),
    }
