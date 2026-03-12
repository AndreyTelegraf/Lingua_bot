from __future__ import annotations

import sqlite3

from services.vocab_runtime.controller import (
    get_next_payload,
    start_controller,
    submit_choice_and_continue,
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute(
        "CREATE TABLE vocab_items (id INTEGER PRIMARY KEY AUTOINCREMENT, lemma TEXT NOT NULL, question_text TEXT NOT NULL, correct_answer TEXT NOT NULL, pos TEXT, is_active INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "CREATE TABLE vocab_choices (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, choice_text TEXT NOT NULL, is_correct INTEGER NOT NULL, position_index INTEGER NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE vocab_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT, status TEXT NOT NULL DEFAULT 'started', total_questions INTEGER DEFAULT 0, correct_answers INTEGER DEFAULT 0, completion_reason TEXT, UNIQUE(user_id, started_at))"
    )
    conn.execute(
        "CREATE TABLE vocab_attempt_events (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, user_id INTEGER NOT NULL, item_id INTEGER NOT NULL, event_type TEXT NOT NULL, answer_text TEXT, is_correct INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(attempt_id) REFERENCES vocab_attempts(id))"
    )
    conn.execute(
        "CREATE TABLE vocab_result_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, step_index INTEGER NOT NULL, estimated_vocab_band TEXT, estimated_vocab_size INTEGER, confidence REAL, snapshot_payload_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )

    conn.executemany(
        "INSERT INTO vocab_items (id, lemma, question_text, correct_answer, pos, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "casa", "casa", "дом", "noun", 1),
            (2, "janela", "janela", "окно", "noun", 1),
        ],
    )
    conn.executemany(
        "INSERT INTO vocab_choices (id, item_id, choice_text, is_correct, position_index) VALUES (?, ?, ?, ?, ?)",
        [
            (101, 1, "дом", 1, 1),
            (102, 1, "окно", 0, 2),
            (103, 1, "книга", 0, 3),
            (104, 1, "вода", 0, 4),
            (105, 1, "стол", 0, 5),
            (106, 1, "дорога", 0, 6),
            (201, 2, "дом", 0, 1),
            (202, 2, "окно", 1, 2),
            (203, 2, "книга", 0, 3),
            (204, 2, "вода", 0, 4),
            (205, 2, "стол", 0, 5),
            (206, 2, "дорога", 0, 6),
        ],
    )
    conn.commit()
    return conn


def test_controller_happy_path() -> None:
    conn = _conn()
    try:
        state = start_controller(conn, user_id=42)
        assert state.status == "in_progress"

        state, payload1 = get_next_payload(conn, state=state)
        assert payload1 is not None
        assert payload1["item_id"] == 1
        assert len(payload1["choices"]) == 6

        state, result1 = submit_choice_and_continue(conn, state=state, choice_id=101)
        assert result1["is_correct"] is True
        assert state.current_item_id is None

        state, payload2 = get_next_payload(conn, state=state)
        assert payload2 is not None
        assert payload2["item_id"] == 2
        assert len(payload2["choices"]) == 6

        state, result2 = submit_choice_and_continue(conn, state=state, choice_id=201)
        assert result2["is_correct"] is False
        assert result2["total_questions"] == 2
        assert result2["correct_answers"] == 1
        assert result2["wrong_answers"] == 1
        assert result2["accuracy_pct"] == 50.0

        state, final_payload = get_next_payload(conn, state=state)
        assert final_payload is not None
        assert final_payload["status"] == "finished"
        assert final_payload["total_questions"] == 2
        assert final_payload["correct_answers"] == 1
        assert final_payload["summary_text"] == "Vocab finished. Score: 1/2 (50%)\nEstimated vocabulary: ~700 words\nBand: <1.5k\nConfidence: 22%"
        assert state.status == "finished"
    finally:
        conn.close()


def test_controller_does_not_reopen_after_finish() -> None:
    conn = _conn()
    try:
        state = start_controller(conn, user_id=42)

        state, payload1 = get_next_payload(conn, state=state)
        assert payload1 is not None
        assert payload1["item_id"] == 1

        state, _ = submit_choice_and_continue(conn, state=state, choice_id=101)

        state, payload2 = get_next_payload(conn, state=state)
        assert payload2 is not None
        assert payload2["item_id"] == 2

        state, _ = submit_choice_and_continue(conn, state=state, choice_id=202)

        state, final_payload = get_next_payload(conn, state=state)
        assert final_payload is not None
        assert final_payload["status"] == "finished"
        assert final_payload["summary_text"] == "Vocab finished. Score: 2/2 (100%)\nEstimated vocabulary: ~700 words\nBand: <1.5k\nConfidence: 30%"
        assert state.status == "finished"

        state2, after_finish = get_next_payload(conn, state=state)
        assert after_finish is not None
        assert after_finish["status"] == "finished"
        assert after_finish["summary_text"] == "Vocab finished. Score: 2/2 (100%)\nEstimated vocabulary: ~700 words\nBand: <1.5k\nConfidence: 30%"
        assert state2.status == "finished"
    finally:
        conn.close()
