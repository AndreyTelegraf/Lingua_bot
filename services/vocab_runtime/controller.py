from __future__ import annotations

import sqlite3

from services.vocab_runtime.flow import answer_choice_step, begin_flow, next_step
from services.vocab_runtime.renderer import build_question_payload
from services.vocab_runtime.state import VocabSessionState


def start_controller(conn: sqlite3.Connection, *, user_id: int) -> VocabSessionState:
    return begin_flow(conn, user_id=user_id)


def get_next_payload(
    conn: sqlite3.Connection,
    *,
    state: VocabSessionState,
) -> tuple[VocabSessionState, dict[str, object] | None]:
    next_state, data = next_step(conn, state=state)
    if data is None:
        return next_state, None

    if next_state.current_item_id is None:
        return next_state, data

    payload = build_question_payload(
        conn,
        item_id=int(next_state.current_item_id),
        attempt_id=int(next_state.attempt_id),
    )
    return next_state, payload


def submit_choice_and_continue(
    conn: sqlite3.Connection,
    *,
    state: VocabSessionState,
    choice_id: int,
) -> tuple[VocabSessionState, dict[str, object]]:
    return answer_choice_step(conn, state=state, choice_id=choice_id)
