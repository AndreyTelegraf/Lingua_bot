from __future__ import annotations

import sqlite3

from services.vocab_runtime.aiogram_mapper import map_answer_result, map_start_result
from services.vocab_runtime.handler_api import answer_callback, start_command


def handle_start(conn: sqlite3.Connection, *, user_id: int) -> dict[str, object]:
    return map_start_result(start_command(conn, user_id=user_id))


def handle_callback(conn: sqlite3.Connection, *, fsm: object, callback_data: str) -> dict[str, object]:
    return map_answer_result(answer_callback(conn, fsm=fsm, callback_data=callback_data))
