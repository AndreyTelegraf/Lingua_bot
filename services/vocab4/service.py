from __future__ import annotations

import sqlite3

from .attempt_state import SelectorState
from .exceptions import AttemptStateError
from .selector import select_next
from . import repo


def start_new_attempt(
    conn: sqlite3.Connection,
    user_id: int,
    question_limit: int = 24,
) -> dict:
    active = repo.load_active_attempt(conn, user_id)
    if active is not None:
        raise AttemptStateError(active["id"], "user already has an active attempt")

    attempt_id = repo.create_attempt(conn, user_id, question_limit)
    repo.start_attempt(conn, attempt_id)

    state = SelectorState.initial()
    pool = repo.load_certified_pool(conn)
    item, new_state = select_next(pool, state)
    repo.persist_selector_state(conn, attempt_id, new_state.to_json())

    return {"attempt_id": attempt_id, "item": item}


def get_next_question(conn: sqlite3.Connection, attempt_id: int) -> dict:
    attempt = repo.load_attempt(conn, attempt_id)
    if attempt is None or attempt["status"] != "in_progress":
        raise AttemptStateError(attempt_id, "attempt is not in_progress")

    pool = repo.load_certified_pool(conn)
    state = SelectorState.from_json(attempt["selector_state_json"])
    item, new_state = select_next(pool, state)
    repo.persist_selector_state(conn, attempt_id, new_state.to_json())

    return {"item": item}


def submit_answer(
    conn: sqlite3.Connection,
    attempt_id: int,
    item_id: int,
    selected_choice_id: int | None,
    is_correct: int,
) -> dict:
    attempt = repo.load_attempt(conn, attempt_id)
    if attempt is None or attempt["status"] != "in_progress":
        raise AttemptStateError(attempt_id, "attempt is not in_progress")

    new_step = attempt["current_step"] + 1
    repo.record_answer_and_advance(
        conn, attempt_id, item_id, selected_choice_id, is_correct, new_step
    )

    if new_step == attempt["question_limit"]:
        repo.finish_attempt(conn, attempt_id)
        return {"status": "finished"}

    return {"status": "in_progress", "next_step": new_step}
