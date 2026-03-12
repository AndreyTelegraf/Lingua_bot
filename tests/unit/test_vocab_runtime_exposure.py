from __future__ import annotations

import sqlite3

from services.vocab_runtime.repo import log_event, start_attempt


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE vocab_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT, status TEXT NOT NULL DEFAULT 'started', total_questions INTEGER DEFAULT 0, correct_answers INTEGER DEFAULT 0, UNIQUE(user_id, started_at))")
    conn.execute("CREATE TABLE vocab_attempt_events (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, user_id INTEGER NOT NULL, item_id INTEGER NOT NULL, event_type TEXT NOT NULL, answer_text TEXT, is_correct INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(attempt_id) REFERENCES vocab_attempts(id))")
    conn.execute("CREATE TABLE vocab_item_exposure (item_id INTEGER PRIMARY KEY, shown_count INTEGER NOT NULL DEFAULT 0, last_shown_at TEXT)")
    conn.commit()
    return conn


def test_log_event_bumps_item_exposure_for_shown() -> None:
    conn = _conn()
    try:
        attempt_id = start_attempt(conn, user_id=42)

        log_event(conn, attempt_id=attempt_id, user_id=42, item_id=1001, event_type="shown")
        log_event(conn, attempt_id=attempt_id, user_id=42, item_id=1001, event_type="shown")

        row = conn.execute(
            "SELECT item_id, shown_count, last_shown_at FROM vocab_item_exposure WHERE item_id = ?",
            (1001,),
        ).fetchone()
        assert row is not None
        assert int(row["item_id"]) == 1001
        assert int(row["shown_count"]) == 2
        assert row["last_shown_at"] is not None
    finally:
        conn.close()


def test_log_event_bumps_item_exposure_for_question_shown() -> None:
    conn = _conn()
    try:
        attempt_id = start_attempt(conn, user_id=77)

        log_event(conn, attempt_id=attempt_id, user_id=77, item_id=2002, event_type="question_shown")

        row = conn.execute(
            "SELECT item_id, shown_count FROM vocab_item_exposure WHERE item_id = ?",
            (2002,),
        ).fetchone()
        assert row is not None
        assert int(row["shown_count"]) == 1
    finally:
        conn.close()


def test_log_event_keeps_answer_counters_working() -> None:
    conn = _conn()
    try:
        attempt_id = start_attempt(conn, user_id=55)

        log_event(conn, attempt_id=attempt_id, user_id=55, item_id=1, event_type="answer", answer_text="x", is_correct=1)
        row = conn.execute(
            "SELECT total_questions, correct_answers FROM vocab_attempts WHERE id = ?",
            (attempt_id,),
        ).fetchone()

        assert row is not None
        assert int(row["total_questions"]) == 1
        assert int(row["correct_answers"]) == 1
    finally:
        conn.close()
