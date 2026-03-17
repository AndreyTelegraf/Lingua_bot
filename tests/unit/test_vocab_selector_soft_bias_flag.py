from __future__ import annotations

import os
import sqlite3

from services.vocab_runtime.attempt_coverage import (
    coverage_priority_order,
    coverage_priority_order_soft_bias,
)
from services.vocab_runtime.selector import _coverage_priority_order_for_runtime


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


def test_runtime_priority_defaults_to_legacy() -> None:
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

    os.environ.pop("VOCAB_SOFT_BIAS_SELECTOR", None)
    got = _coverage_priority_order_for_runtime(conn, attempt_id=200, total_questions=24)
    want = coverage_priority_order(conn, attempt_id=200, total_questions=24)
    assert got == want


def test_runtime_priority_uses_soft_bias_under_flag() -> None:
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

    os.environ["VOCAB_SOFT_BIAS_SELECTOR"] = "1"
    try:
        got = _coverage_priority_order_for_runtime(conn, attempt_id=200, total_questions=24)
        want = coverage_priority_order_soft_bias(conn, attempt_id=200, total_questions=24)
        assert got == want
    finally:
        os.environ.pop("VOCAB_SOFT_BIAS_SELECTOR", None)
