"""
Unit tests for scripts/noun10k_monitoring_runner.py.

Uses an in-memory SQLite DB with controlled test fixtures.
These tests do NOT touch data/lingua_staging.db and make no network calls.
All test data is synthetic and labeled as such; verdicts from this test
suite are NOT decision-supporting.
"""
from __future__ import annotations

import sqlite3
import statistics

import pytest

from scripts.noun10k_monitoring_runner import (
    MINIMUM_SESSIONS,
    MINIMUM_USERS,
    T1_REPEAT_RATE_CONCERN,
    T2_MEAN_ITEMS_DEPLETION,
    T3_MIN_ITEMS_WITH_3_SHOWN,
    T4_SKEW_MEDIAN_THRESHOLD,
    T4_SKEW_TOP_THRESHOLD,
    build_report,
    evaluate_triggers,
    fetch_real_session_ids,
    fetch_real_session_user_count,
    fetch_signal1_items_per_session,
    fetch_signal2_exposure_per_item,
    fetch_signal3_repeat_rate,
    fetch_signal4_correctness,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_db() -> sqlite3.Connection:
    """Create minimal in-memory DB schema for monitoring runner tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            telegram_user_id INTEGER,
            username TEXT,
            first_name TEXT,
            is_bot INTEGER DEFAULT 0
        );

        CREATE TABLE vocab_attempts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            mode_run_id INTEGER,
            status TEXT NOT NULL,
            completion_reason TEXT,
            started_at TEXT,
            finished_at TEXT
        );

        CREATE TABLE vocab_items (
            id INTEGER PRIMARY KEY,
            lemma TEXT NOT NULL,
            pos TEXT NOT NULL,
            bin_name TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            cefr_estimate TEXT
        );

        CREATE TABLE vocab_answers (
            id INTEGER PRIMARY KEY,
            attempt_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            is_correct INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE vocab_item_exposure (
            item_id INTEGER PRIMARY KEY,
            shown_count INTEGER DEFAULT 0,
            answered_count INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            last_shown_at TEXT,
            last_answered_at TEXT
        );
        """
    )
    return conn


def _add_noun10k_items(conn: sqlite3.Connection, count: int, start_id: int = 1) -> list[int]:
    ids = list(range(start_id, start_id + count))
    for i in ids:
        conn.execute(
            "INSERT INTO vocab_items (id, lemma, pos, bin_name, is_active, cefr_estimate) "
            "VALUES (?, ?, 'noun', '10K', 1, 'B2')",
            (i, f"lemma_{i}"),
        )
    conn.commit()
    return ids


def _add_session(
    conn: sqlite3.Connection,
    session_id: int,
    user_id: int,
    completion_reason: str = "question_limit_reached",
    status: str = "finished",
) -> None:
    conn.execute(
        "INSERT INTO vocab_attempts (id, user_id, status, completion_reason) VALUES (?, ?, ?, ?)",
        (session_id, user_id, status, completion_reason),
    )
    conn.commit()


def _add_answer(
    conn: sqlite3.Connection,
    answer_id: int,
    attempt_id: int,
    item_id: int,
    is_correct: int = 1,
) -> None:
    conn.execute(
        "INSERT INTO vocab_answers (id, attempt_id, item_id, is_correct) VALUES (?, ?, ?, ?)",
        (answer_id, attempt_id, item_id, is_correct),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Real session filter tests
# ---------------------------------------------------------------------------


def test_fetch_real_session_ids_excludes_simulation_exhausted():
    conn = _make_db()
    _add_session(conn, 1, user_id=10, completion_reason="question_limit_reached")
    _add_session(conn, 2, user_id=11, completion_reason="simulation_exhausted")
    _add_session(conn, 3, user_id=12, completion_reason=None, status="started")

    ids = fetch_real_session_ids(conn)
    assert ids == [1], "Only question_limit_reached should be returned"


def test_fetch_real_session_ids_empty_db():
    conn = _make_db()
    ids = fetch_real_session_ids(conn)
    assert ids == []


def test_fetch_real_session_user_count():
    conn = _make_db()
    _add_session(conn, 1, user_id=10)
    _add_session(conn, 2, user_id=10)
    _add_session(conn, 3, user_id=11)
    ids = fetch_real_session_ids(conn)
    count = fetch_real_session_user_count(conn, ids)
    assert count == 2


# ---------------------------------------------------------------------------
# Signal 1 tests
# ---------------------------------------------------------------------------


def test_signal1_counts_noun10k_per_session():
    conn = _make_db()
    item_ids = _add_noun10k_items(conn, 3)
    _add_session(conn, 1, user_id=10)
    _add_session(conn, 2, user_id=10)

    _add_answer(conn, 1, attempt_id=1, item_id=item_ids[0])
    _add_answer(conn, 2, attempt_id=1, item_id=item_ids[1])
    _add_answer(conn, 3, attempt_id=2, item_id=item_ids[2])

    ids = fetch_real_session_ids(conn)
    result = fetch_signal1_items_per_session(conn, ids)

    assert len(result) == 2
    shown = {r["attempt_id"]: r["noun10k_shown"] for r in result}
    assert shown[1] == 2
    assert shown[2] == 1


def test_signal1_empty_sessions():
    conn = _make_db()
    result = fetch_signal1_items_per_session(conn, [])
    assert result == []


def test_signal1_excludes_non_noun10k():
    conn = _make_db()
    conn.execute(
        "INSERT INTO vocab_items (id, lemma, pos, bin_name, is_active) "
        "VALUES (99, 'verb_item', 'verb', '5K', 1)"
    )
    conn.commit()
    _add_session(conn, 1, user_id=10)
    _add_answer(conn, 1, attempt_id=1, item_id=99)

    ids = fetch_real_session_ids(conn)
    result = fetch_signal1_items_per_session(conn, ids)
    assert result == [], "Verb items should not count toward noun/10K signal"


def test_signal1_excludes_inactive_noun10k():
    conn = _make_db()
    # Active item
    conn.execute(
        "INSERT INTO vocab_items (id, lemma, pos, bin_name, is_active) "
        "VALUES (1, 'active_lemma', 'noun', '10K', 1)"
    )
    # Inactive legacy item
    conn.execute(
        "INSERT INTO vocab_items (id, lemma, pos, bin_name, is_active) "
        "VALUES (2, 'legacy_lemma', 'noun', '10K', 0)"
    )
    conn.commit()
    _add_session(conn, 1, user_id=10)
    _add_answer(conn, 1, attempt_id=1, item_id=1)
    _add_answer(conn, 2, attempt_id=1, item_id=2)

    ids = fetch_real_session_ids(conn)
    result = fetch_signal1_items_per_session(conn, ids)
    assert len(result) == 1
    assert result[0]["noun10k_shown"] == 1, "Inactive noun/10K item must not be counted"


# ---------------------------------------------------------------------------
# Signal 2 tests
# ---------------------------------------------------------------------------


def test_signal2_counts_sessions_shown():
    conn = _make_db()
    item_ids = _add_noun10k_items(conn, 2)
    _add_session(conn, 1, user_id=10)
    _add_session(conn, 2, user_id=11)

    _add_answer(conn, 1, attempt_id=1, item_id=item_ids[0])
    _add_answer(conn, 2, attempt_id=2, item_id=item_ids[0])
    _add_answer(conn, 3, attempt_id=1, item_id=item_ids[1])

    ids = fetch_real_session_ids(conn)
    result = fetch_signal2_exposure_per_item(conn, ids)

    by_id = {r["item_id"]: r for r in result}
    assert by_id[item_ids[0]]["sessions_shown"] == 2
    assert by_id[item_ids[1]]["sessions_shown"] == 1


def test_signal2_zero_for_unseen_item():
    conn = _make_db()
    item_ids = _add_noun10k_items(conn, 2)
    _add_session(conn, 1, user_id=10)
    _add_answer(conn, 1, attempt_id=1, item_id=item_ids[0])

    ids = fetch_real_session_ids(conn)
    result = fetch_signal2_exposure_per_item(conn, ids)

    by_id = {r["item_id"]: r for r in result}
    assert by_id[item_ids[1]]["sessions_shown"] == 0


# ---------------------------------------------------------------------------
# Signal 3 tests
# ---------------------------------------------------------------------------


def test_signal3_no_repeat():
    conn = _make_db()
    item_ids = _add_noun10k_items(conn, 4)
    _add_session(conn, 1, user_id=10)
    _add_session(conn, 2, user_id=10)

    _add_answer(conn, 1, 1, item_ids[0])
    _add_answer(conn, 2, 1, item_ids[1])
    _add_answer(conn, 3, 2, item_ids[2])
    _add_answer(conn, 4, 2, item_ids[3])

    ids = fetch_real_session_ids(conn)
    result = fetch_signal3_repeat_rate(conn, ids)

    assert result["pairs_evaluated"] == 1
    assert result["mean_repeat_rate"] == 0.0


def test_signal3_full_repeat():
    conn = _make_db()
    item_ids = _add_noun10k_items(conn, 2)
    _add_session(conn, 1, user_id=10)
    _add_session(conn, 2, user_id=10)

    for aid, iid in [(1, item_ids[0]), (2, item_ids[1])]:
        _add_answer(conn, aid, 1, iid)
    for aid, iid in [(3, item_ids[0]), (4, item_ids[1])]:
        _add_answer(conn, aid, 2, iid)

    ids = fetch_real_session_ids(conn)
    result = fetch_signal3_repeat_rate(conn, ids)

    assert result["pairs_evaluated"] == 1
    assert result["mean_repeat_rate"] == 1.0


def test_signal3_single_session_no_pairs():
    conn = _make_db()
    item_ids = _add_noun10k_items(conn, 2)
    _add_session(conn, 1, user_id=10)
    _add_answer(conn, 1, 1, item_ids[0])

    ids = fetch_real_session_ids(conn)
    result = fetch_signal3_repeat_rate(conn, ids)

    assert result["pairs_evaluated"] == 0


def test_signal3_excludes_inactive_noun10k():
    conn = _make_db()
    # Active item used in both sessions
    conn.execute(
        "INSERT INTO vocab_items (id, lemma, pos, bin_name, is_active) "
        "VALUES (1, 'active_lemma', 'noun', '10K', 1)"
    )
    # Inactive legacy item — would create a false repeat if included
    conn.execute(
        "INSERT INTO vocab_items (id, lemma, pos, bin_name, is_active) "
        "VALUES (2, 'legacy_lemma', 'noun', '10K', 0)"
    )
    conn.commit()
    _add_session(conn, 1, user_id=10)
    _add_session(conn, 2, user_id=10)
    # Session 1: active + legacy; Session 2: legacy only
    _add_answer(conn, 1, 1, 1)
    _add_answer(conn, 2, 1, 2)
    _add_answer(conn, 3, 2, 2)

    ids = fetch_real_session_ids(conn)
    result = fetch_signal3_repeat_rate(conn, ids)
    # After filtering inactive: session 1 has {1}, session 2 has {}
    # Pair is skipped (curr_items empty) → 0 pairs evaluated
    assert result["pairs_evaluated"] == 0, (
        "Inactive noun/10K items must not contribute to repeat-rate pairs"
    )


# ---------------------------------------------------------------------------
# Signal 4 tests
# ---------------------------------------------------------------------------


def test_signal4_min_5_answers():
    conn = _make_db()
    item_ids = _add_noun10k_items(conn, 1)

    for sess_id in range(1, 4):
        _add_session(conn, sess_id, user_id=10 + sess_id)
    answer_id = 1
    for sess_id in range(1, 4):
        _add_answer(conn, answer_id, sess_id, item_ids[0], is_correct=1)
        answer_id += 1

    ids = fetch_real_session_ids(conn)
    result = fetch_signal4_correctness(conn, ids)
    assert result == [], "Items with fewer than 5 answers must not appear"


def test_signal4_correctness_computed():
    conn = _make_db()
    item_ids = _add_noun10k_items(conn, 1)

    for sess_id in range(1, 6):
        _add_session(conn, sess_id, user_id=100 + sess_id)

    answer_id = 1
    for i, sess_id in enumerate(range(1, 6), start=1):
        correct = 1 if i <= 4 else 0
        _add_answer(conn, answer_id, sess_id, item_ids[0], is_correct=correct)
        answer_id += 1

    ids = fetch_real_session_ids(conn)
    result = fetch_signal4_correctness(conn, ids)

    assert len(result) == 1
    assert result[0]["total_answers"] == 5
    assert result[0]["correct_count"] == 4
    assert result[0]["pct_correct"] == 80.0


# ---------------------------------------------------------------------------
# Trigger evaluation tests
# ---------------------------------------------------------------------------


def _make_signal2(shown_counts: list[int]) -> list[dict]:
    return [
        {"item_id": i, "lemma": f"lemma_{i}", "sessions_shown": c, "total_answers": c}
        for i, c in enumerate(shown_counts, start=1)
    ]


def test_verdict_insufficient_data_below_minimum_sessions():
    result = evaluate_triggers(
        session_ids=list(range(1, 20)),
        distinct_users=3,
        signal1=[{"attempt_id": i, "noun10k_shown": 2} for i in range(1, 20)],
        signal2=_make_signal2([2] * 13),
        signal3={"pairs_evaluated": 5, "mean_repeat_rate": 0.1, "max_repeat_rate": 0.2},
        signal4=[],
    )
    assert result["verdict"] == "INSUFFICIENT_DATA"
    assert result["minimum_sample_met"] is False


def test_verdict_insufficient_data_below_minimum_users():
    result = evaluate_triggers(
        session_ids=list(range(1, 35)),
        distinct_users=2,
        signal1=[{"attempt_id": i, "noun10k_shown": 2} for i in range(1, 35)],
        signal2=_make_signal2([5] * 13),
        signal3={"pairs_evaluated": 10, "mean_repeat_rate": 0.1, "max_repeat_rate": 0.2},
        signal4=[],
    )
    assert result["verdict"] == "INSUFFICIENT_DATA"


def test_verdict_hold_when_no_triggers():
    result = evaluate_triggers(
        session_ids=list(range(1, 31)),
        distinct_users=3,
        signal1=[{"attempt_id": i, "noun10k_shown": 2} for i in range(1, 31)],
        signal2=_make_signal2([5] * 13),
        signal3={"pairs_evaluated": 10, "mean_repeat_rate": 0.1, "max_repeat_rate": 0.2},
        signal4=[],
    )
    assert result["verdict"] == "HOLD"
    assert result["minimum_sample_met"] is True
    assert result["T1"]["fires"] is False
    assert result["T2"]["fires"] is False
    assert result["T3"]["fires"] is False
    assert result["T4"]["fires"] is False


def test_t1_fires_on_high_repeat_rate():
    result = evaluate_triggers(
        session_ids=list(range(1, 31)),
        distinct_users=3,
        signal1=[{"attempt_id": i, "noun10k_shown": 2} for i in range(1, 31)],
        signal2=_make_signal2([5] * 13),
        signal3={"pairs_evaluated": 10, "mean_repeat_rate": 0.5, "max_repeat_rate": 0.7},
        signal4=[],
    )
    assert result["T1"]["fires"] is True
    assert result["verdict"] == "PREPARE_NEXT_TRANCHE"


def test_t2_fires_on_low_items_per_session():
    result = evaluate_triggers(
        session_ids=list(range(1, 31)),
        distinct_users=3,
        signal1=[{"attempt_id": i, "noun10k_shown": 1} for i in range(1, 31)],
        signal2=_make_signal2([5] * 13),
        signal3={"pairs_evaluated": 10, "mean_repeat_rate": 0.1, "max_repeat_rate": 0.2},
        signal4=[],
    )
    assert result["T2"]["fires"] is True
    assert result["verdict"] == "PREPARE_NEXT_TRANCHE"


def test_t3_fires_on_coverage_failure():
    shown = [4] * 9 + [0] * 4
    result = evaluate_triggers(
        session_ids=list(range(1, 31)),
        distinct_users=3,
        signal1=[{"attempt_id": i, "noun10k_shown": 2} for i in range(1, 31)],
        signal2=_make_signal2(shown),
        signal3={"pairs_evaluated": 10, "mean_repeat_rate": 0.1, "max_repeat_rate": 0.2},
        signal4=[],
    )
    assert result["T3"]["fires"] is True
    assert result["verdict"] == "PREPARE_NEXT_TRANCHE"


def test_t4_fires_on_exposure_skew():
    shown = [12] + [1] * 12
    result = evaluate_triggers(
        session_ids=list(range(1, 31)),
        distinct_users=3,
        signal1=[{"attempt_id": i, "noun10k_shown": 2} for i in range(1, 31)],
        signal2=_make_signal2(shown),
        signal3={"pairs_evaluated": 10, "mean_repeat_rate": 0.1, "max_repeat_rate": 0.2},
        signal4=[],
    )
    assert result["T4"]["fires"] is True
    assert result["verdict"] == "PREPARE_NEXT_TRANCHE"


def test_investigate_signal_on_broken_item():
    result = evaluate_triggers(
        session_ids=list(range(1, 31)),
        distinct_users=3,
        signal1=[{"attempt_id": i, "noun10k_shown": 2} for i in range(1, 31)],
        signal2=_make_signal2([5] * 13),
        signal3={"pairs_evaluated": 10, "mean_repeat_rate": 0.1, "max_repeat_rate": 0.2},
        signal4=[
            {
                "item_id": 1,
                "lemma": "cotovelo",
                "cefr_estimate": "B2",
                "total_answers": 10,
                "correct_count": 1,
                "pct_correct": 10.0,
            }
        ],
    )
    assert result["verdict"] == "INVESTIGATE_SIGNAL"


# ---------------------------------------------------------------------------
# End-to-end: build_report against in-memory DB
# ---------------------------------------------------------------------------


def test_build_report_insufficient_data():
    conn = _make_db()
    _add_noun10k_items(conn, 13)
    _add_session(conn, 1, user_id=10)

    report = build_report(conn)
    assert report["verdict"] == "INSUFFICIENT_DATA"
    assert report["summary"]["total_real_sessions"] == 1


def test_build_report_excludes_simulation_sessions():
    conn = _make_db()
    _add_noun10k_items(conn, 13)
    _add_session(conn, 1, user_id=10, completion_reason="simulation_exhausted")
    _add_session(conn, 2, user_id=11, completion_reason="question_limit_reached")

    report = build_report(conn)
    assert report["summary"]["total_real_sessions"] == 1


def test_build_report_hold_with_sufficient_data():
    conn = _make_db()
    item_ids = _add_noun10k_items(conn, 13)

    # 30 distinct users, 1 session each → no consecutive pairs → T1 (repeat) = None → no fire.
    # Each session shows 2 items, cycling through all 13 → each item seen ~5 times → T3 ok.
    # max sessions_shown ≈ 5 < T4 threshold 8 → T4 no fire.
    # mean items/session = 2 ≥ 1.5 → T2 no fire.
    answer_id = 1
    for i in range(30):
        sess_id = i + 1
        user_id = 200 + i
        _add_session(conn, sess_id, user_id=user_id)
        iid_a = item_ids[(2 * i) % 13]
        iid_b = item_ids[(2 * i + 1) % 13]
        _add_answer(conn, answer_id, sess_id, iid_a, is_correct=1)
        answer_id += 1
        _add_answer(conn, answer_id, sess_id, iid_b, is_correct=1)
        answer_id += 1

    report = build_report(conn)
    assert report["summary"]["total_real_sessions"] == 30
    assert report["summary"]["distinct_real_users"] == 30
    assert report["verdict"] == "HOLD"
