from __future__ import annotations

import sqlite3

from services.vocab_runtime.controller import (
    get_next_payload,
    start_controller,
    submit_choice_and_continue,
)
from services.vocab_runtime.fsm import VocabFSM, attach_state
from services.vocab_runtime.state import VocabSessionState


def start_vocab_session(conn: sqlite3.Connection, *, user_id: int) -> VocabFSM:
    state = start_controller(conn, user_id=user_id)
    return VocabFSM(state=state)


def get_vocab_question(
    conn: sqlite3.Connection,
    *,
    fsm: VocabFSM,
) -> tuple[VocabFSM, dict[str, object] | None]:
    state, payload = get_next_payload(conn, state=fsm.state)
    return attach_state(fsm, state), payload


def submit_vocab_choice(
    conn: sqlite3.Connection,
    *,
    fsm: VocabFSM,
    choice_id: int,
) -> tuple[VocabFSM, dict[str, object]]:
    state, result = submit_choice_and_continue(conn, state=fsm.state, choice_id=choice_id)
    return attach_state(fsm, state), result
