from __future__ import annotations

import sqlite3

from services.vocab_runtime.attempt_coverage import (
    coverage_priority_order,
    coverage_soft_bias_weights,
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


def test_soft_bias_weights_raise_unseen_pos_even_if_legacy_order_is_noun_first() -> None:
    conn = _make_conn()
    conn.executemany(
        "INSERT INTO vocab_items(id, is_active, pos, freq_rank, bin_name) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, "noun", 10, "1k"),
            (2, 1, "noun", 20, "1k"),
            (3, 1, "noun", 30, "1k"),
            (4, 1, "verb", 40, "1k"),
            (5, 1, "adjective", 50, "1k"),
            (6, 1, "adverb", 60, "1k"),
        ],
    )
    conn.executemany(
        "INSERT INTO vocab_answers(attempt_id, item_id) VALUES (?, ?)",
        [(200, 1), (200, 2), (200, 3)],
    )

    remaining = remaining_targets_for_attempt(conn, attempt_id=200, total_questions=24)
    assert remaining == {"noun": 9, "verb": 4, "adjective": 4, "adverb": 4}

    legacy_order = coverage_priority_order(conn, attempt_id=200, total_questions=24)
    assert legacy_order[0] == "noun"

    weights = coverage_soft_bias_weights(conn, attempt_id=200, total_questions=24)
    assert weights["verb"] > weights["noun"]
    assert weights["adjective"] > weights["noun"]
    assert weights["adverb"] > weights["noun"]


def test_soft_bias_weights_are_equal_when_nothing_seen() -> None:
    conn = _make_conn()
    conn.executemany(
        "INSERT INTO vocab_items(id, is_active, pos, freq_rank, bin_name) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, "noun", 10, "1k"),
            (2, 1, "verb", 20, "1k"),
            (3, 1, "adjective", 30, "1k"),
            (4, 1, "adverb", 40, "1k"),
        ],
    )
    weights = coverage_soft_bias_weights(conn, attempt_id=1, total_questions=24)
    assert weights["noun"] == weights["verb"] == weights["adjective"] == weights["adverb"]
