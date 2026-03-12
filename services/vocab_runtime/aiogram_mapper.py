from __future__ import annotations

from services.vocab_runtime.handler_api import answer_callback, start_command


def map_start_result(result: tuple[object, dict[str, object] | None]) -> dict[str, object]:
    fsm, view = result
    return {
        "fsm": fsm,
        "view": view,
    }


def map_answer_result(result: tuple[object, dict[str, object]]) -> dict[str, object]:
    fsm, payload = result
    return {
        "fsm": fsm,
        "answer_result": payload["answer_result"],
        "next_view": payload["next_view"],
    }
