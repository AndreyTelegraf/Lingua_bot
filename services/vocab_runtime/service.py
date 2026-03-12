from __future__ import annotations

import sqlite3

from services.vocab_runtime.repo import (
    finish_attempt,
    get_active_attempt,
    get_attempt_stats,
    log_event,
    start_attempt,
)
from services.vocab_runtime.selector import get_next_item


def start_or_resume_attempt(conn: sqlite3.Connection, *, user_id: int) -> dict[str, object]:
    attempt_id = start_attempt(conn, user_id=user_id)
    return get_attempt_stats(conn, attempt_id=attempt_id)


def get_next_question(conn: sqlite3.Connection, *, user_id: int) -> dict[str, object] | None:
    active = get_active_attempt(conn, user_id=user_id)
    if active is None:
        attempt_id = start_attempt(conn, user_id=user_id)
    else:
        attempt_id = int(active["id"])

    item = get_next_item(conn, attempt_id=attempt_id)
    if item is None:
        return None

    log_event(
        conn,
        attempt_id=attempt_id,
        user_id=user_id,
        item_id=int(item["id"]),
        event_type="shown",
    )

    return {
        "attempt_id": attempt_id,
        "item_id": int(item["id"]),
        "lemma": str(item["lemma"]),
        "question_text": str(item["question_text"]),
        "correct_answer": str(item["correct_answer"]),
        "pos": str(item["pos"] or ""),
    }


def submit_answer(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    attempt_id: int,
    item_id: int,
    answer_text: str | None,
) -> dict[str, object]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT correct_answer FROM vocab_items WHERE id = ?",
        (item_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError("item_not_found")

    correct_answer = str(row["correct_answer"])
    is_correct = 1 if (answer_text or "").strip().casefold() == correct_answer.strip().casefold() else 0

    log_event(
        conn,
        attempt_id=attempt_id,
        user_id=user_id,
        item_id=item_id,
        event_type="answer",
        answer_text=answer_text,
        is_correct=is_correct,
    )

    stats = get_attempt_stats(conn, attempt_id=attempt_id)
    return {
        "is_correct": bool(is_correct),
        "correct_answer": correct_answer,
        "total_questions": stats["total_questions"],
        "correct_answers": stats["correct_answers"],
    }


def finish_active_attempt(conn: sqlite3.Connection, *, user_id: int) -> dict[str, object] | None:
    active = get_active_attempt(conn, user_id=user_id)
    if active is None:
        return None

    attempt_id = int(active["id"])
    finish_attempt(conn, attempt_id=attempt_id)
    return get_attempt_stats(conn, attempt_id=attempt_id)


def submit_choice(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    attempt_id: int,
    item_id: int,
    choice_id: int,
) -> dict[str, object]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        'SELECT choice_text, is_correct FROM vocab_choices WHERE id = ? AND item_id = ?',
        (choice_id, item_id),
    ).fetchone()
    if row is None:
        raise RuntimeError("choice_not_found")

    answer_text = str(row["choice_text"])
    is_correct = int(row["is_correct"])

    log_event(
        conn,
        attempt_id=attempt_id,
        user_id=user_id,
        item_id=item_id,
        event_type="answer",
        answer_text=answer_text,
        is_correct=is_correct,
    )

    stats = get_attempt_stats(conn, attempt_id=attempt_id)
    return {
        "is_correct": bool(is_correct),
        "correct_answer": answer_text if is_correct else None,
        "selected_answer": answer_text,
        "total_questions": stats["total_questions"],
        "correct_answers": stats["correct_answers"],
    }
