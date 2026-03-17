from __future__ import annotations

import sqlite3

from services.vocab_runtime.attempt_coverage import (
    coverage_priority_order,
    get_attempt_coverage_snapshot,
    remaining_targets_for_attempt,
)


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        '''
        CREATE TABLE vocab_items (
            id INTEGER PRIMARY KEY,
            is_active INTEGER NOT NULL,
            pos TEXT,
            freq_rank INTEGER,
            bin_name TEXT
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE vocab_answers (
            id INTEGER PRIMARY KEY,
            attempt_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL
        )
        '''
    )
    return conn


def test_remaining_targets_for_24_question_attempt() -> None:
    conn = _make_conn()
    conn.executemany(
        "INSERT INTO vocab_items(id, is_active, pos, freq_rank, bin_name) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, "noun", 10, "1k"),
            (2, 1, "noun", 20, "1k"),
            (3, 1, "verb", 30, "1k"),
            (4, 1, "adjective", 40, "1k"),
            (5, 1, "adverb", 50, "1k"),
        ],
    )
    conn.executemany(
        "INSERT INTO vocab_answers(attempt_id, item_id) VALUES (?, ?)",
        [(100, 1), (100, 2), (100, 3)],
    )

    remaining = remaining_targets_for_attempt(conn, attempt_id=100, total_questions=24)
    assert remaining == {
        "noun": 10,
        "verb": 3,
        "adjective": 4,
        "adverb": 4,
    }


def test_priority_order_prefers_most_missing_pos() -> None:
    conn = _make_conn()
    conn.executemany(
        "INSERT INTO vocab_items(id, is_active, pos, freq_rank, bin_name) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, "noun", 10, "1k"),
            (2, 1, "noun", 20, "1k"),
            (3, 1, "noun", 30, "1k"),
            (4, 1, "verb", 40, "1k"),
        ],
    )
    conn.executemany(
        "INSERT INTO vocab_answers(attempt_id, item_id) VALUES (?, ?)",
        [(200, 1), (200, 2), (200, 3)],
    )

    order = coverage_priority_order(conn, attempt_id=200, total_questions=24)
    assert order[0] == "noun"
    assert order == ["noun", "adjective", "adverb", "verb"]


def test_snapshot_falls_back_cleanly_without_pos_column() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        '''
        CREATE TABLE vocab_items (
            id INTEGER PRIMARY KEY,
            is_active INTEGER NOT NULL,
            freq_rank INTEGER,
            bin_name TEXT
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE vocab_answers (
            id INTEGER PRIMARY KEY,
            attempt_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL
        )
        '''
    )
    snapshot = get_attempt_coverage_snapshot(conn, attempt_id=1, total_questions=24)
    assert snapshot["observed_pos_counts"] == {}
    assert snapshot["remaining_pos_targets"]["noun"] == 12
