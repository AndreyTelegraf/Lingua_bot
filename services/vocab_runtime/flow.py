from __future__ import annotations

import sqlite3

from services.vocab_runtime.repo import get_attempt_stats
from services.vocab_runtime.service import (
    finish_active_attempt,
    get_next_question,
    start_or_resume_attempt,
    submit_answer,
    submit_choice,
)
from services.vocab_runtime.state import (
    VocabSessionState,
    clear_current_question,
    finish_session,
    set_current_question,
    start_session,
)


def begin_flow(conn: sqlite3.Connection, *, user_id: int) -> VocabSessionState:
    attempt = start_or_resume_attempt(conn, user_id=user_id)
    return start_session(user_id=user_id, attempt_id=int(attempt["attempt_id"]))


def next_step(conn: sqlite3.Connection, *, state: VocabSessionState) -> tuple[VocabSessionState, dict[str, object] | None]:
    if state.status == "finished":
        if state.attempt_id is None:
            return state, {"status": "finished", "attempt_id": None}
        return state, get_attempt_stats(conn, attempt_id=int(state.attempt_id))

    question = get_next_question(conn, user_id=state.user_id)
    if question is None:
        finished = finish_active_attempt(conn, user_id=state.user_id, completion_reason="items_exhausted")
        next_state = finish_session(state)
        return next_state, finished if finished is not None else {"status": "finished", "attempt_id": state.attempt_id}

    next_state = set_current_question(state, item_id=int(question["item_id"]))
    return next_state, question


def answer_step(
    conn: sqlite3.Connection,
    *,
    state: VocabSessionState,
    answer_text: str | None,
) -> tuple[VocabSessionState, dict[str, object]]:
    if state.attempt_id is None or state.current_item_id is None:
        raise RuntimeError("no_active_question")

    result = submit_answer(
        conn,
        user_id=state.user_id,
        attempt_id=int(state.attempt_id),
        item_id=int(state.current_item_id),
        answer_text=answer_text,
    )
    next_state = clear_current_question(state)
    return next_state, result


def answer_choice_step(
    conn: sqlite3.Connection,
    *,
    state: VocabSessionState,
    choice_id: int,
) -> tuple[VocabSessionState, dict[str, object]]:
    if state.attempt_id is None or state.current_item_id is None:
        raise RuntimeError("no_active_question")

    result = submit_choice(
        conn,
        user_id=state.user_id,
        attempt_id=int(state.attempt_id),
        item_id=int(state.current_item_id),
        choice_id=choice_id,
    )
    next_state = clear_current_question(state)
    return next_state, result
