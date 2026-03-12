from __future__ import annotations

import sqlite3

from services.vocab_runtime.service import (
    finish_active_attempt,
    get_next_question,
    start_or_resume_attempt,
    submit_answer,
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute(
        "CREATE TABLE vocab_items (id INTEGER PRIMARY KEY AUTOINCREMENT, lemma TEXT NOT NULL, question_text TEXT NOT NULL, correct_answer TEXT NOT NULL, pos TEXT, freq_rank INTEGER, bin_name TEXT, is_active INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute(
        "CREATE TABLE vocab_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT, status TEXT NOT NULL DEFAULT 'started', total_questions INTEGER DEFAULT 0, correct_answers INTEGER DEFAULT 0, completion_reason TEXT, estimated_vocab_band TEXT, estimated_vocab_size INTEGER, confidence REAL, UNIQUE(user_id, started_at))"
    )
    conn.execute(
        "CREATE TABLE vocab_attempt_events (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, user_id INTEGER NOT NULL, item_id INTEGER NOT NULL, event_type TEXT NOT NULL, answer_text TEXT, is_correct INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(attempt_id) REFERENCES vocab_attempts(id))"
    )
    conn.execute(
        "CREATE TABLE vocab_result_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, step_index INTEGER NOT NULL, estimated_vocab_band TEXT, estimated_vocab_size INTEGER, confidence REAL, snapshot_payload_json TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE vocab_item_exposure (item_id INTEGER PRIMARY KEY, shown_count INTEGER NOT NULL DEFAULT 0, last_shown_at TEXT)"
    )

    conn.executemany(
        "INSERT INTO vocab_items (lemma, question_text, correct_answer, pos, freq_rank, bin_name, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("casa", "casa", "дом", "noun", 800, "1K", 1),
            ("janela", "janela", "окно", "noun", 1800, "2K", 1),
            ("raro", "raro", "редкий", "adj", 5200, "6K", 1),
        ],
    )

    conn.commit()
    return conn


def test_service_happy_path() -> None:
    conn = _conn()
    try:
        attempt = start_or_resume_attempt(conn, user_id=42)
        assert attempt["status"] == "started"

        q1 = get_next_question(conn, user_id=42)
        assert q1 is not None
        assert q1["item_id"] == 1

        r1 = submit_answer(
            conn,
            user_id=42,
            attempt_id=int(q1["attempt_id"]),
            item_id=int(q1["item_id"]),
            answer_text="дом",
        )
        assert r1["is_correct"] is True
        assert r1["total_questions"] == 1
        assert r1["correct_answers"] == 1
        assert r1["wrong_answers"] == 0
        assert r1["accuracy_pct"] == 100.0
        assert r1["estimated_vocab_size"] == 9000
        assert r1["estimated_vocab_band"] == "8k+"
        assert r1["confidence"] == 0.33
        assert r1["scoring_model"] == "runtime_scoring_v1"

        q2 = get_next_question(conn, user_id=42)
        assert q2 is not None
        assert q2["item_id"] == 2

        r2 = submit_answer(
            conn,
            user_id=42,
            attempt_id=int(q2["attempt_id"]),
            item_id=int(q2["item_id"]),
            answer_text="неправильный ответ",
        )
        assert r2["is_correct"] is False
        assert r2["total_questions"] == 2
        assert r2["correct_answers"] == 1
        assert r2["wrong_answers"] == 1
        assert r2["accuracy_pct"] == 50.0
        assert r2["estimated_vocab_size"] == 2200
        assert r2["estimated_vocab_band"] == "1.5k-2.5k"
        assert r2["confidence"] == 0.32
        assert r2["sample_score"] == 0.083

        finished = finish_active_attempt(conn, user_id=42)
        assert finished is not None
        assert finished["status"] == "finished"
        assert finished["total_questions"] == 2
        assert finished["correct_answers"] == 1
        assert finished["wrong_answers"] == 1
        assert finished["accuracy_pct"] == 50.0
        assert finished["estimated_vocab_size"] == 2200
        assert finished["estimated_vocab_band"] == "1.5k-2.5k"
        assert finished["confidence"] == 0.32
        assert finished["scoring_model"] == "runtime_scoring_v1"
        assert "Estimated vocabulary: ~2200 words" in finished["summary_text"]
        assert "Band: 1.5k-2.5k" in finished["summary_text"]
        assert finished["completion_reason"] == "items_exhausted"

        row = conn.execute(
            "SELECT step_index, estimated_vocab_size FROM vocab_result_snapshots WHERE attempt_id = ?",
            (int(q1["attempt_id"]),),
        ).fetchone()
        assert row is not None
        assert int(row["step_index"]) == 2
        assert int(row["estimated_vocab_size"]) == 2200
    finally:
        conn.close()


def test_submit_choice_happy_path() -> None:
    conn = _conn()
    try:
        conn.execute(
            "CREATE TABLE vocab_choices (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, choice_text TEXT NOT NULL, is_correct INTEGER NOT NULL, position_index INTEGER NOT NULL)"
        )
        conn.executemany(
            "INSERT INTO vocab_choices (id, item_id, choice_text, is_correct, position_index) VALUES (?, ?, ?, ?, ?)",
            [
                (101, 1, "дом", 1, 1),
                (102, 1, "окно", 0, 2),
            ],
        )
        conn.commit()

        from services.vocab_runtime.service import submit_choice

        attempt = start_or_resume_attempt(conn, user_id=42)
        result = submit_choice(
            conn,
            user_id=42,
            attempt_id=int(attempt["attempt_id"]),
            item_id=1,
            choice_id=101,
        )
        assert result["is_correct"] is True
        assert result["selected_answer"] == "дом"
        assert result["total_questions"] == 1
        assert result["correct_answers"] == 1
        assert result["estimated_vocab_band"] == "8k+"
    finally:
        conn.close()
