from __future__ import annotations

import sqlite3

from services.vocab_runtime.repo import get_active_user_baseline, persist_finished_result


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute("CREATE TABLE vocab_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, status TEXT NOT NULL, total_questions INTEGER DEFAULT 0, correct_answers INTEGER DEFAULT 0, estimated_vocab_size INTEGER, estimated_vocab_band TEXT, confidence REAL, started_at TEXT DEFAULT CURRENT_TIMESTAMP, finished_at TEXT, mode_run_id INTEGER)")
    conn.execute("CREATE TABLE vocab_attempt_events (id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, event_type TEXT NOT NULL, item_id INTEGER, is_correct INTEGER, payload_json TEXT)")
    conn.execute("CREATE TABLE vocab_items (id INTEGER PRIMARY KEY AUTOINCREMENT, bin_name TEXT, freq_rank INTEGER)")
    conn.execute("CREATE TABLE user_mode_baselines (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, mode TEXT NOT NULL, baseline_version TEXT NOT NULL, source_mode TEXT NOT NULL, source_run_id INTEGER, source_attempt_id INTEGER, estimated_vocab_size INTEGER, estimated_vocab_band TEXT, estimated_cefr_level TEXT, confidence REAL, calibration_payload_json TEXT, valid_from TEXT DEFAULT CURRENT_TIMESTAMP, valid_until TEXT, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE TABLE user_progress_events (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, mode TEXT NOT NULL, source_run_id INTEGER, source_attempt_id INTEGER, event_type TEXT NOT NULL, previous_payload_json TEXT, current_payload_json TEXT NOT NULL, delta_payload_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    return conn


def _seed_attempt(conn: sqlite3.Connection, *, user_id: int, attempt_id: int, correct: int, total: int, band: str, size: int):
    conn.execute("INSERT INTO vocab_attempts (id, user_id, status, total_questions, correct_answers, estimated_vocab_size, estimated_vocab_band, confidence) VALUES (?, ?, 'finished', ?, ?, ?, ?, 0.8)", (attempt_id, user_id, total, correct, size, band))
    conn.commit()


def test_persist_finished_result_creates_and_rotates_vocab_baseline():
    conn = _conn()
    try:
        _seed_attempt(conn, user_id=7, attempt_id=1, correct=12, total=24, band='1.5k-2.5k', size=1800)
        first = persist_finished_result(conn, attempt_id=1)
        baseline1 = get_active_user_baseline(conn, user_id=7, mode='vocab')
        assert baseline1 is not None
        assert baseline1['estimated_vocab_band'] == '1.5k-2.5k'
        assert first.get('previous_correct_answers') is None

        _seed_attempt(conn, user_id=7, attempt_id=2, correct=16, total=24, band='2.5k-4k', size=3200)
        second = persist_finished_result(conn, attempt_id=2)
        baseline2 = get_active_user_baseline(conn, user_id=7, mode='vocab')
        assert baseline2 is not None
        assert baseline2['estimated_vocab_band'] == '2.5k-4k'
        assert second['previous_correct_answers'] == 12
        assert second['previous_total_questions'] == 24
        assert second['previous_estimated_vocab_band'] == '1.5k-2.5k'

        events = conn.execute("SELECT event_type FROM user_progress_events ORDER BY id").fetchall()
        assert [r['event_type'] for r in events] == ['baseline_created', 'result_improved']
    finally:
        conn.close()
