from __future__ import annotations

import sqlite3

from services.vocab_runtime.aiogram_mapper import map_answer_result, map_start_result
from services.vocab_runtime.handler_api import answer_callback, start_command


def handle_start(conn: sqlite3.Connection, *, user_id: int) -> dict[str, object]:
    raw = start_command(conn, user_id=user_id)
    mapped = map_start_result(raw)
    return mapped

def handle_callback(conn: sqlite3.Connection, *, fsm: object, callback_data: str) -> dict[str, object]:
    raw = answer_callback(conn, fsm=fsm, callback_data=callback_data)
    mapped = map_answer_result(raw)
    return mapped
