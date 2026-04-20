"""
Unit tests for the synthetic session harness and monitoring exclusion.

All tests use in-memory SQLite — no data/lingua_staging.db access.
These sessions are synthetic by design and never authorize tranche decisions.
"""
from __future__ import annotations

import random
import sqlite3
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from scripts.noun10k_monitoring_runner import (
    REAL_SESSION_FILTER,
    SYNTHETIC_SESSION_COMPLETION_REASON,
    SYNTHETIC_SESSION_SOURCE,
    fetch_real_session_ids,
    fetch_real_session_user_count,
)
from scripts.run_synthetic_vocab_sessions import (
    _PROFILES,
    _PROFILE_NAMES,
    _upsert_synthetic_user,
    run_session,
    run_profile,
)


# ---------------------------------------------------------------------------
# Minimal in-memory schema for harness tests
# ---------------------------------------------------------------------------

_HARNESS_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    is_bot INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE mode_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    source TEXT,
    completion_reason TEXT,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE vocab_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode_run_id INTEGER,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'started',
    completion_reason TEXT,
    current_step INTEGER NOT NULL DEFAULT 0,
    question_limit INTEGER NOT NULL DEFAULT 4,
    questions_answered INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    dont_know_count INTEGER NOT NULL DEFAULT 0,
    total_reject_count INTEGER NOT NULL DEFAULT 0,
    hard_reject_streak INTEGER NOT NULL DEFAULT 0,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE vocab_items (
    id INTEGER PRIMARY KEY,
    lemma TEXT NOT NULL,
    question_text TEXT NOT NULL DEFAULT 'Что значит?',
    pos TEXT NOT NULL,
    bin_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    correct_answer TEXT NOT NULL DEFAULT 'answer',
    cefr_estimate TEXT,
    freq_rank INTEGER,
    level TEXT,
    concept_group TEXT,
    donor_eligible INTEGER DEFAULT 0
);
CREATE TABLE vocab_choices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    choice_text TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    position_index INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE vocab_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    selected_choice_id INTEGER,
    answer_status TEXT NOT NULL DEFAULT 'correct',
    answer_kind TEXT NOT NULL DEFAULT 'selected',
    is_correct INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(attempt_id, item_id)
);
CREATE TABLE vocab_attempt_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    item_id INTEGER,
    event_type TEXT NOT NULL,
    answer_text TEXT,
    is_correct INTEGER,
    step_index INTEGER,
    reason_code TEXT,
    payload_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE vocab_item_exposure (
    item_id INTEGER PRIMARY KEY,
    shown_count INTEGER NOT NULL DEFAULT 0,
    answered_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    last_shown_at TEXT,
    last_answered_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _make_harness_db(n_items: int = 10) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_HARNESS_SCHEMA)

    for i in range(1, n_items + 1):
        pos = ["noun", "verb", "adjective", "adverb"][i % 4]
        bin_name = ["1K", "2K", "5K", "10K"][i % 4]
        conn.execute(
            "INSERT INTO vocab_items (id, lemma, pos, bin_name, is_active, correct_answer, freq_rank) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)",
            (i, f"lemma_{i}", pos, bin_name, f"answer_{i}", i * 10),
        )
        conn.execute(
            "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (?, ?, 1, 0)",
            (i, f"answer_{i}"),
        )
        for j in range(1, 4):
            conn.execute(
                "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (?, ?, 0, ?)",
                (i, f"distractor_{i}_{j}", j),
            )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------

class TestSyntheticConstants:
    def test_source_constant(self):
        assert SYNTHETIC_SESSION_SOURCE == "synthetic_harness"

    def test_completion_reason_constant(self):
        assert SYNTHETIC_SESSION_COMPLETION_REASON == "simulation_exhausted"

    def test_profiles_defined(self):
        for p in ("strong", "medium", "weak", "dont_know_heavy"):
            assert p in _PROFILES
            assert "correct_rate" in _PROFILES[p]
            assert "dont_know_rate" in _PROFILES[p]

    def test_profile_rates_in_range(self):
        for name, cfg in _PROFILES.items():
            assert 0.0 <= cfg["correct_rate"] <= 1.0, name
            assert 0.0 <= cfg["dont_know_rate"] <= 1.0, name

    def test_filter_excludes_simulation_exhausted(self):
        # The monitoring SQL filter must NOT match simulation_exhausted
        assert "question_limit_reached" in REAL_SESSION_FILTER
        assert "simulation_exhausted" not in REAL_SESSION_FILTER


# ---------------------------------------------------------------------------
# User upsert tests
# ---------------------------------------------------------------------------

class TestSyntheticUserUpsert:
    def test_upsert_creates_user(self):
        conn = _make_harness_db()
        user_id = _upsert_synthetic_user(conn, profile="strong")
        assert isinstance(user_id, int)
        assert user_id > 0

    def test_upsert_marks_is_bot(self):
        conn = _make_harness_db()
        user_id = _upsert_synthetic_user(conn, profile="medium")
        row = conn.execute("SELECT is_bot FROM users WHERE id = ?", (user_id,)).fetchone()
        assert row["is_bot"] == 1

    def test_upsert_idempotent(self):
        conn = _make_harness_db()
        id1 = _upsert_synthetic_user(conn, profile="weak")
        id2 = _upsert_synthetic_user(conn, profile="weak")
        assert id1 == id2

    def test_different_profiles_different_users(self):
        conn = _make_harness_db()
        id_strong = _upsert_synthetic_user(conn, profile="strong")
        id_weak = _upsert_synthetic_user(conn, profile="weak")
        assert id_strong != id_weak


# ---------------------------------------------------------------------------
# Session creation tests
# ---------------------------------------------------------------------------

class TestRunSession:
    def test_session_written_to_db(self):
        conn = _make_harness_db()
        user_id = _upsert_synthetic_user(conn, profile="medium")
        rng = random.Random(42)
        result = run_session(conn, user_id=user_id, profile="medium", question_limit=4,
                             rng=rng, dry_run=False, verbose=False)
        attempt_id = result["attempt_id"]
        row = conn.execute(
            "SELECT status, completion_reason FROM vocab_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        assert row is not None
        assert row["status"] == "finished"

    def test_completion_reason_is_simulation_exhausted(self):
        conn = _make_harness_db()
        user_id = _upsert_synthetic_user(conn, profile="strong")
        rng = random.Random(1)
        result = run_session(conn, user_id=user_id, profile="strong", question_limit=4,
                             rng=rng, dry_run=False, verbose=False)
        attempt_id = result["attempt_id"]
        row = conn.execute(
            "SELECT completion_reason FROM vocab_attempts WHERE id = ?", (attempt_id,)
        ).fetchone()
        assert row["completion_reason"] == SYNTHETIC_SESSION_COMPLETION_REASON

    def test_mode_run_source_is_synthetic_harness(self):
        conn = _make_harness_db()
        user_id = _upsert_synthetic_user(conn, profile="weak")
        rng = random.Random(7)
        result = run_session(conn, user_id=user_id, profile="weak", question_limit=4,
                             rng=rng, dry_run=False, verbose=False)
        mode_run_id = result["mode_run_id"]
        row = conn.execute(
            "SELECT source FROM mode_runs WHERE id = ?", (mode_run_id,)
        ).fetchone()
        assert row["source"] == SYNTHETIC_SESSION_SOURCE

    def test_vocab_answers_written(self):
        conn = _make_harness_db()
        user_id = _upsert_synthetic_user(conn, profile="strong")
        rng = random.Random(5)
        result = run_session(conn, user_id=user_id, profile="strong", question_limit=4,
                             rng=rng, dry_run=False, verbose=False)
        attempt_id = result["attempt_id"]
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM vocab_answers WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()["cnt"]
        assert count > 0

    def test_dry_run_writes_nothing(self):
        conn = _make_harness_db()
        rng = random.Random(99)
        before_attempts = conn.execute("SELECT COUNT(*) as c FROM vocab_attempts").fetchone()["c"]
        run_session(conn, user_id=999, profile="medium", question_limit=4,
                    rng=rng, dry_run=True, verbose=False)
        after_attempts = conn.execute("SELECT COUNT(*) as c FROM vocab_attempts").fetchone()["c"]
        assert after_attempts == before_attempts

    def test_returns_result_dict_with_expected_keys(self):
        conn = _make_harness_db()
        user_id = _upsert_synthetic_user(conn, profile="medium")
        rng = random.Random(3)
        result = run_session(conn, user_id=user_id, profile="medium", question_limit=4,
                             rng=rng, dry_run=False, verbose=False)
        for key in ("attempt_id", "mode_run_id", "questions_answered", "correct_count",
                    "dont_know_count", "source", "completion_reason"):
            assert key in result, f"Missing key: {key}"

    def test_questions_answered_le_limit(self):
        conn = _make_harness_db()
        user_id = _upsert_synthetic_user(conn, profile="strong")
        rng = random.Random(42)
        result = run_session(conn, user_id=user_id, profile="strong", question_limit=4,
                             rng=rng, dry_run=False, verbose=False)
        assert result["questions_answered"] <= 4


# ---------------------------------------------------------------------------
# Monitoring exclusion tests
# ---------------------------------------------------------------------------

class TestMonitoringExclusion:
    def _make_monitoring_db(self) -> sqlite3.Connection:
        """Minimal schema matching monitoring runner expectations."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE vocab_attempts (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                mode_run_id INTEGER,
                status TEXT NOT NULL,
                completion_reason TEXT
            );
        """)
        return conn

    def _add_attempt(self, conn, aid, user_id, completion_reason, status="finished"):
        conn.execute(
            "INSERT INTO vocab_attempts (id, user_id, status, completion_reason) VALUES (?, ?, ?, ?)",
            (aid, user_id, status, completion_reason),
        )
        conn.commit()

    def test_synthetic_session_excluded_from_live_filter(self):
        conn = self._make_monitoring_db()
        self._add_attempt(conn, 1, user_id=10, completion_reason="question_limit_reached")
        self._add_attempt(conn, 2, user_id=11, completion_reason=SYNTHETIC_SESSION_COMPLETION_REASON)
        live_ids = fetch_real_session_ids(conn)
        assert 1 in live_ids
        assert 2 not in live_ids

    def test_only_question_limit_reached_counted(self):
        conn = self._make_monitoring_db()
        for i in range(1, 6):
            self._add_attempt(conn, i, user_id=i, completion_reason="question_limit_reached")
        for i in range(6, 11):
            self._add_attempt(conn, i, user_id=i, completion_reason=SYNTHETIC_SESSION_COMPLETION_REASON)
        live_ids = fetch_real_session_ids(conn)
        assert len(live_ids) == 5
        assert all(i in live_ids for i in range(1, 6))
        assert not any(i in live_ids for i in range(6, 11))

    def test_synthetic_sessions_do_not_affect_user_count(self):
        conn = self._make_monitoring_db()
        self._add_attempt(conn, 1, user_id=10, completion_reason="question_limit_reached")
        self._add_attempt(conn, 2, user_id=10, completion_reason="question_limit_reached")
        self._add_attempt(conn, 3, user_id=99, completion_reason=SYNTHETIC_SESSION_COMPLETION_REASON)
        self._add_attempt(conn, 4, user_id=88, completion_reason=SYNTHETIC_SESSION_COMPLETION_REASON)
        live_ids = fetch_real_session_ids(conn)
        user_count = fetch_real_session_user_count(conn, live_ids)
        assert user_count == 1  # only user_id=10


# ---------------------------------------------------------------------------
# Profile count test
# ---------------------------------------------------------------------------

def test_all_four_profiles_defined():
    for name in ("strong", "medium", "weak", "dont_know_heavy"):
        assert name in _PROFILES
