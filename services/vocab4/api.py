from __future__ import annotations

import sqlite3

from services.vocab4 import repo, service
from services.vocab4 import result as result_module


def start_attempt(
    conn: sqlite3.Connection,
    user_id: int,
    question_limit: int = 24,
) -> dict:
    return service.start_new_attempt(conn, user_id=user_id, question_limit=question_limit)


def next_question(
    conn: sqlite3.Connection,
    attempt_id: int,
) -> dict:
    return service.get_next_question(conn, attempt_id)


def submit_answer(
    conn: sqlite3.Connection,
    attempt_id: int,
    item_id: int,
    selected_choice_id: int | None,
    is_correct: int,
) -> dict:
    outcome = service.submit_answer(conn, attempt_id, item_id, selected_choice_id, is_correct)

    if outcome["status"] == "in_progress":
        return {"status": "in_progress", "next_step": outcome["next_step"]}

    attempt = repo.load_attempt(conn, attempt_id)
    if attempt is None:
        raise RuntimeError(f"attempt_id={attempt_id} not found")

    answers = repo.load_answers_for_attempt(conn, attempt_id)
    pool    = repo.load_certified_pool(conn)
    result  = result_module.build_result(attempt, answers, pool)
    return {"status": "finished", "result": result}
