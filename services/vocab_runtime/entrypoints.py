from __future__ import annotations

from services.vocab_runtime.aiogram_handlers_contract import (
    callback_handler_contract,
    start_handler_contract,
)


def run_vocab_start(*, conn, user_id: int) -> dict[str, object]:
    return start_handler_contract(conn=conn, user_id=user_id)


def run_vocab_callback(*, conn, fsm, callback_data: str) -> dict[str, object]:
    return callback_handler_contract(conn=conn, fsm=fsm, callback_data=callback_data)
