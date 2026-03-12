from __future__ import annotations

import json
import sqlite3

from services.vocab_runtime.repo import finish_attempt, get_attempt_stats, log_event, persist_finished_result, start_attempt


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE vocab_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, mode_run_id INTEGER, user_id INTEGER NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT, status TEXT NOT NULL DEFAULT 'started', total_questions INTEGER DEFAULT 0, correct_answers INTEGER DEFAULT 0, completion_reason TEXT, estimated_vocab_band TEXT, estimated_vocab_size INTEGER, confidence REAL, UNIQUE(user_id, started_at))"
    )
    conn.execute(
        "CREATE TABLE vocab_attempt_events (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, user_id INTEGER NOT NULL, item_id INTEGER NOT NULL, event_type TEXT NOT NULL, answer_text TEXT, is_correct INTEGER, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "CREATE TABLE vocab_items (id INTEGER PRIMARY KEY, lemma TEXT NOT NULL, question_text TEXT NOT NULL, correct_answer TEXT NOT NULL, pos TEXT, freq_rank INTEGER, bin_name TEXT, is_active INTEGER NOT NULL DEFAULT 1)"
    )
    conn.execute(
        "CREATE TABLE vocab_item_exposure (item_id INTEGER PRIMARY KEY, shown_count INTEGER NOT NULL DEFAULT 0, last_shown_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE vocab_result_snapshots (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, step_index INTEGER NOT NULL, estimated_vocab_band TEXT, estimated_vocab_size INTEGER, confidence REAL, snapshot_payload_json TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE mode_results (id INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT NOT NULL, run_id INTEGER NOT NULL, user_id INTEGER NOT NULL, result_version TEXT NOT NULL DEFAULT 'v1', score_numeric REAL, band_text TEXT, cefr_level TEXT, confidence REAL, result_payload_json TEXT NOT NULL)"
    )
    conn.executemany(
        "INSERT INTO vocab_items (id, lemma, question_text, correct_answer, pos, freq_rank, bin_name, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "casa", "casa", "дом", "noun", 800, "1K", 1),
            (2, "janela", "janela", "окно", "noun", 1800, "2K", 1),
            (3, "raro", "raro", "редкий", "adj", 5200, "6K", 1),
        ],
    )
    conn.commit()
    return conn


def test_repo_happy_path() -> None:
    conn = _conn()
    try:
        attempt_id = start_attempt(conn, user_id=42)
        log_event(conn, attempt_id=attempt_id, user_id=42, item_id=1, event_type="shown")
        log_event(conn, attempt_id=attempt_id, user_id=42, item_id=1, event_type="answer", answer_text="дом", is_correct=1)

        stats = get_attempt_stats(conn, attempt_id=attempt_id)
        assert stats["status"] == "started"
        assert stats["total_questions"] == 1
        assert stats["correct_answers"] == 1
        assert stats["wrong_answers"] == 0
        assert stats["accuracy_pct"] == 100.0
        assert stats["estimated_vocab_size"] == 9000
        assert stats["estimated_vocab_band"] == "8k+"
        assert stats["confidence"] == 0.33
        assert stats["scoring_model"] == "runtime_scoring_v1"
        assert "Estimated vocabulary: ~9000 words" in stats["summary_text"]

        finish_attempt(conn, attempt_id=attempt_id, completion_reason="items_exhausted")
        stats2 = get_attempt_stats(conn, attempt_id=attempt_id)
        assert stats2["status"] == "finished"
        assert stats2["finished_at"] is not None
        assert stats2["completion_reason"] == "items_exhausted"
    finally:
        conn.close()


def test_persist_finished_result_writes_snapshot_and_mode_result() -> None:
    conn = _conn()
    try:
        attempt_id = start_attempt(conn, user_id=77)
        conn.execute("UPDATE vocab_attempts SET mode_run_id = 9001 WHERE id = ?", (attempt_id,))
        conn.commit()

        log_event(conn, attempt_id=attempt_id, user_id=77, item_id=1, event_type="answer", answer_text="дом", is_correct=1)
        log_event(conn, attempt_id=attempt_id, user_id=77, item_id=3, event_type="answer", answer_text="x", is_correct=0)
        finish_attempt(conn, attempt_id=attempt_id, completion_reason="items_exhausted")

        stats = persist_finished_result(conn, attempt_id=attempt_id)
        assert stats["total_questions"] == 2
        assert stats["correct_answers"] == 1
        assert stats["wrong_answers"] == 1
        assert stats["accuracy_pct"] == 50.0
        assert stats["completion_reason"] == "items_exhausted"
        assert stats["estimated_vocab_size"] == 2200
        assert stats["estimated_vocab_band"] == "1.5k-2.5k"
        assert stats["confidence"] == 0.45
        assert stats["weighted_bin_hits"]["1K"] > 0

        row = conn.execute(
            "SELECT step_index, estimated_vocab_band, estimated_vocab_size, confidence, snapshot_payload_json FROM vocab_result_snapshots WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        assert row is not None
        assert int(row["step_index"]) == 2
        assert row["estimated_vocab_band"] == "1.5k-2.5k"
        assert int(row["estimated_vocab_size"]) == 2200
        payload = json.loads(row["snapshot_payload_json"])
        assert payload["estimated_vocab_size"] == 2200
        assert payload["scoring_model"] == "runtime_scoring_v1"

        row = conn.execute(
            "SELECT mode, run_id, score_numeric, band_text, confidence, result_version, result_payload_json FROM mode_results WHERE run_id = ?",
            (9001,),
        ).fetchone()
        assert row is not None
        assert row["mode"] == "vocab"
        assert float(row["score_numeric"]) == 50.0
        assert row["band_text"] == "1.5k-2.5k"
        assert row["result_version"] == "runtime_scoring_v1"
        payload = json.loads(row["result_payload_json"])
        assert payload["estimated_vocab_band"] == "1.5k-2.5k"
        assert payload["weighted_bin_hits"]["1K"] > 0
    finally:
        conn.close()
