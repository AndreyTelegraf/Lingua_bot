from __future__ import annotations

import sqlite3

from services.vocab_runtime.repo import log_event, start_attempt
from services.vocab_runtime.selector import get_next_item


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE vocab_items (id INTEGER PRIMARY KEY AUTOINCREMENT, lemma TEXT NOT NULL, question_text TEXT NOT NULL, correct_answer TEXT NOT NULL, pos TEXT, is_active INTEGER NOT NULL DEFAULT 0)")
    conn.execute("CREATE TABLE vocab_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT, status TEXT NOT NULL DEFAULT started, total_questions INTEGER DEFAULT 0, correct_answers INTEGER DEFAULT 0, UNIQUE(user_id, started_at))")
    conn.execute("CREATE TABLE vocab_attempt_events (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, user_id INTEGER NOT NULL, item_id INTEGER NOT NULL, event_type TEXT NOT NULL, answer_text TEXT, is_correct INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(attempt_id) REFERENCES vocab_attempts(id))")
    conn.executemany(
        "INSERT INTO vocab_items (lemma, question_text, correct_answer, pos, is_active) VALUES (?, ?, ?, ?, ?)",
        [
            ("casa", "casa", "дом", "noun", 1),
            ("janela", "janela", "окно", "noun", 1),
            ("livro", "livro", "книга", "noun", 1),
        ],
    )
    return conn


def test_get_next_item_skips_already_shown_items() -> None:
    conn = _conn()
    try:
        attempt_id = start_attempt(conn, user_id=42)

        first = get_next_item(conn, attempt_id=attempt_id)
        assert first is not None
        assert int(first["id"]) == 1
        log_event(conn, attempt_id=attempt_id, user_id=42, item_id=int(first["id"]), event_type="shown")

        second = get_next_item(conn, attempt_id=attempt_id)
        assert second is not None
        assert int(second["id"]) == 2
        log_event(conn, attempt_id=attempt_id, user_id=42, item_id=int(second["id"]), event_type="shown")

        third = get_next_item(conn, attempt_id=attempt_id)
        assert third is not None
        assert int(third["id"]) == 3
        log_event(conn, attempt_id=attempt_id, user_id=42, item_id=int(third["id"]), event_type="shown")

        none_left = get_next_item(conn, attempt_id=attempt_id)
        assert none_left is None
    finally:
        conn.close()
