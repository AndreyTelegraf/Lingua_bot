from __future__ import annotations

import sqlite3

from services.vocab_runtime.app import (
    get_vocab_question,
    start_vocab_session,
    submit_vocab_choice,
)
from services.vocab_runtime.callbacks import decode_choice_callback
from services.vocab_runtime.fsm import VocabFSM
from services.vocab_runtime.telegram_adapter import build_telegram_question_view


def start_command(conn: sqlite3.Connection, *, user_id: int) -> tuple[VocabFSM, dict[str, object] | None]:
    fsm = start_vocab_session(conn, user_id=user_id)
    fsm, payload = get_vocab_question(conn, fsm=fsm)
    if payload is None:
        return fsm, None
    if 'choices' not in payload:
        return fsm, payload
    view = build_telegram_question_view(payload)
    return fsm, view

def answer_callback(
    conn: sqlite3.Connection,
    *,
    fsm: VocabFSM,
    callback_data: str,
) -> tuple[VocabFSM, dict[str, object]]:
    choice_id = decode_choice_callback(callback_data)
    fsm, result = submit_vocab_choice(conn, fsm=fsm, choice_id=choice_id)
    fsm, next_payload = get_vocab_question(conn, fsm=fsm)


    if next_payload is None:
        return fsm, {'answer_result': result, 'next_view': None}

    if 'choices' in next_payload:
        next_view = build_telegram_question_view(next_payload)
    else:
        next_view = next_payload


    return fsm, {
        'answer_result': result,
        'next_view': next_view,
    }
