from __future__ import annotations

import sqlite3

from services.vocab_runtime.repo import finish_attempt, get_active_attempt, get_attempt_stats, log_event, start_attempt


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE vocab_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT, status TEXT NOT NULL DEFAULT 'started', total_questions INTEGER DEFAULT 0, correct_answers INTEGER DEFAULT 0, UNIQUE(user_id, started_at))"
    )
    conn.execute(
        "CREATE TABLE vocab_attempt_events (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, user_id INTEGER NOT NULL, item_id INTEGER NOT NULL, event_type TEXT NOT NULL, answer_text TEXT, is_correct INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(attempt_id) REFERENCES vocab_attempts(id))"
    )
    return conn


def test_attempt_repo_smoke() -> None:
    conn = _conn()
    try:
        attempt_id = start_attempt(conn, user_id=42)
        assert attempt_id > 0

        same_attempt_id = start_attempt(conn, user_id=42)
        assert same_attempt_id == attempt_id

        active = get_active_attempt(conn, user_id=42)
        assert active is not None
        assert int(active["id"]) == attempt_id

        event1 = log_event(conn, attempt_id=attempt_id, user_id=42, item_id=1001, event_type="shown")
        assert event1 > 0

        event2 = log_event(conn, attempt_id=attempt_id, user_id=42, item_id=1001, event_type="answer", answer_text="дом", is_correct=1)
        assert event2 > 0

        stats = get_attempt_stats(conn, attempt_id=attempt_id)
        assert stats["status"] == "started"
        assert stats["total_questions"] == 1
        assert stats["correct_answers"] == 1

        finish_attempt(conn, attempt_id=attempt_id)

        stats2 = get_attempt_stats(conn, attempt_id=attempt_id)
        assert stats2["status"] == "finished"
        assert stats2["finished_at"] is not None

        active2 = get_active_attempt(conn, user_id=42)
        assert active2 is None
    finally:
        conn.close()
