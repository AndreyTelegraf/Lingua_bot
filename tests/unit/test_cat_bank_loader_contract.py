from __future__ import annotations

import sqlite3

from services.cat_runtime.bank_loader import (
    CATBankLoadStats,
    load_cat_item_bank_from_vocab,
    load_vocab_rows_for_cat,
    summarize_vocab_rows_eligibility,
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE vocab_items (
            id INTEGER PRIMARY KEY,
            lemma TEXT,
            question_text TEXT,
            correct_answer TEXT,
            freq_rank INTEGER,
            bin_name TEXT,
            level TEXT,
            topic_tag TEXT,
            pos TEXT,
            is_active INTEGER,
            difficulty_b REAL
        )
        """
    )
    return conn


def test_load_vocab_rows_for_cat_reads_rows_from_vocab_items() -> None:
    conn = _conn()
    try:
        conn.executemany(
            """
            INSERT INTO vocab_items
            (id, lemma, question_text, correct_answer, is_active)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "casa", "q1", "a1", 1),
                (2, "livro", "q2", "a2", 1),
            ],
        )
        conn.commit()

        rows = load_vocab_rows_for_cat(conn)
        assert len(rows) == 2
        assert rows[0]["id"] == 1
        assert rows[1]["lemma"] == "livro"
    finally:
        conn.close()


def test_summarize_vocab_rows_eligibility_counts_skips() -> None:
    rows = [
        {"id": 1, "lemma": "casa", "question_text": "q1", "correct_answer": "a1", "is_active": 1},
        {"id": 2, "lemma": "livro", "question_text": "", "correct_answer": "a2", "is_active": 1},
        {"id": 3, "lemma": "", "question_text": "", "correct_answer": "a3", "is_active": 1},
        {"id": 4, "lemma": "rio", "question_text": "q4", "correct_answer": "", "is_active": 1},
        {"id": 5, "lemma": "mar", "question_text": "q5", "correct_answer": "a5", "is_active": 0},
    ]

    stats = summarize_vocab_rows_eligibility(rows, active_only=True)

    assert isinstance(stats, CATBankLoadStats)
    assert stats.total_rows == 5
    assert stats.eligible_rows == 2
    assert stats.skipped_missing_question == 1
    assert stats.skipped_missing_answer == 1
    assert stats.skipped_inactive == 1


def test_load_cat_item_bank_from_vocab_filters_ineligible_rows() -> None:
    conn = _conn()
    try:
        conn.executemany(
            """
            INSERT INTO vocab_items
            (id, lemma, question_text, correct_answer, freq_rank, bin_name, level, topic_tag, pos, is_active, difficulty_b)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "casa", "Choose casa", "house", 100, "1K", "A1", "home", "noun", 1, None),
                (2, "livro", "", "", 200, "1K", "A1", "home", "noun", 1, None),
                (3, "rio", "Choose rio", "river", 3000, "5K", "A2", "nature", "noun", 0, None),
                (4, "abrir", "Choose abrir", "open", 1200, "2K", "A2", "verbs", "verb", 1, 0.55),
            ],
        )
        conn.commit()

        items = load_cat_item_bank_from_vocab(conn, active_only=True)

        assert [x.item_id for x in items] == [1, 4]
        assert items[0].answer_key == "house"
        assert items[1].difficulty_b == 0.55
    finally:
        conn.close()


def test_load_cat_item_bank_from_vocab_returns_empty_when_table_missing() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        items = load_cat_item_bank_from_vocab(conn)
        assert items == []
    finally:
        conn.close()
