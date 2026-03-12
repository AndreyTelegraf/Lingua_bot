from __future__ import annotations

import sqlite3
from typing import Any


def start_attempt(conn: sqlite3.Connection, *, user_id: int) -> int:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id FROM vocab_attempts WHERE user_id = ? AND status = 'started' ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row is not None:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO vocab_attempts (user_id, status, total_questions, correct_answers) VALUES (?, 'started', 0, 0)",
        (user_id,),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_active_attempt(conn: sqlite3.Connection, *, user_id: int) -> sqlite3.Row | None:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT * FROM vocab_attempts WHERE user_id = ? AND status = 'started' ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()


def log_event(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    user_id: int,
    item_id: int,
    event_type: str,
    answer_text: str | None = None,
    is_correct: int | None = None,
) -> int:
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "INSERT INTO vocab_attempt_events (attempt_id, user_id, item_id, event_type, answer_text, is_correct) VALUES (?, ?, ?, ?, ?, ?)",
        (attempt_id, user_id, item_id, event_type, answer_text, is_correct),
    )
    if event_type in ("answer", "dont_know"):
        conn.execute(
            "UPDATE vocab_attempts SET total_questions = COALESCE(total_questions, 0) + 1, correct_answers = COALESCE(correct_answers, 0) + CASE WHEN COALESCE(?, 0) = 1 THEN 1 ELSE 0 END WHERE id = ?",
            (is_correct, attempt_id),
        )
    conn.commit()
    return int(cur.lastrowid)


def finish_attempt(conn: sqlite3.Connection, *, attempt_id: int, status: str = "finished") -> None:
    conn.execute(
        "UPDATE vocab_attempts SET status = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'started'",
        (status, attempt_id),
    )
    conn.commit()


def get_attempt_stats(conn: sqlite3.Connection, *, attempt_id: int) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, user_id, status, total_questions, correct_answers, started_at, finished_at FROM vocab_attempts WHERE id = ?",
        (attempt_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError("attempt_not_found")
    return {
        "attempt_id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "status": str(row["status"]),
        "total_questions": int(row["total_questions"] or 0),
        "correct_answers": int(row["correct_answers"] or 0),
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }
