from __future__ import annotations

import sqlite3

from services.vocab_bank.build_items import (
    assign_bin_name,
    build_vocab_items_from_candidates,
)


def _prepare_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute(
        """
        CREATE TABLE vocab_lemma_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            build_id INTEGER,
            source_name TEXT NOT NULL,
            source_weight REAL,
            merge_group_id TEXT,
            normalized_lemma TEXT NOT NULL,
            lemma_key TEXT NOT NULL,
            pos TEXT,
            level TEXT,
            freq_rank INTEGER,
            ru_gloss TEXT,
            gloss_key TEXT,
            is_eligible INTEGER NOT NULL DEFAULT 1,
            reject_reason TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE vocab_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma TEXT NOT NULL,
            question_text TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            pos TEXT,
            level TEXT,
            freq_rank INTEGER,
            bin_name TEXT,
            topic_tag TEXT,
            is_active INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    return conn


def test_assign_bin_name_smoke() -> None:
    assert assign_bin_name(300) == "1K"
    assert assign_bin_name(1700) == "2K"
    assert assign_bin_name(3600) == "5K"
    assert assign_bin_name(7000) == "10K"
    assert assign_bin_name(15000) == "20K"
    assert assign_bin_name(50000) == "rare"
    assert assign_bin_name(None) == "rare"


def test_build_vocab_items_from_candidates_smoke() -> None:
    conn = _prepare_conn()
    try:
        conn.executemany(
            """
            INSERT INTO vocab_lemma_candidates (
                source_name, merge_group_id, normalized_lemma, lemma_key, pos, level, freq_rank, ru_gloss, gloss_key, is_eligible, reject_reason, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("sample_csv", "casa::noun", "casa", "casa", "noun", "A1", 300, "дом", "дом", 1, None, "{}"),
                ("sample_csv", "trabalhar::verb", "trabalhar", "trabalhar", "verb", "A1", 980, "работать", "работать", 1, None, "{}"),
                ("sample_csv", "bad::noun", "x", "x", "noun", "A1", 99999, "икс", "икс", 0, "lemma_too_short", "{}"),
            ],
        )
        conn.commit()

        inserted = build_vocab_items_from_candidates(
            conn,
            source_name="sample_csv",
            truncate_topic_prefix=None,
        )
        assert inserted == 2

        rows = conn.execute(
            """
            SELECT lemma, question_text, correct_answer, pos, level, freq_rank, bin_name, topic_tag, is_active
            FROM vocab_items
            ORDER BY id
            """
        ).fetchall()

        assert len(rows) == 2
        assert rows[0]["lemma"] == "casa"
        assert rows[0]["question_text"] == "casa"
        assert rows[0]["correct_answer"] == "дом"
        assert rows[0]["bin_name"] == "1K"
        assert rows[0]["topic_tag"] == "build:sample_csv"
        assert rows[0]["is_active"] == 0
        assert rows[1]["bin_name"] == "1K"
    finally:
        conn.close()


def test_build_vocab_items_truncate_topic_prefix() -> None:
    conn = _prepare_conn()
    try:
        conn.execute(
            """
            INSERT INTO vocab_items (
                lemma, question_text, correct_answer, pos, level, freq_rank, bin_name, topic_tag, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("old", "old", "старый", "noun", "A1", 100, "1K", "build:sample_csv", 0),
        )
        conn.execute(
            """
            INSERT INTO vocab_lemma_candidates (
                source_name, merge_group_id, normalized_lemma, lemma_key, pos, level, freq_rank, ru_gloss, gloss_key, is_eligible, reject_reason, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sample_csv", "janela::noun", "janela", "janela", "noun", "A2", 1700, "окно", "окно", 1, None, "{}"),
        )
        conn.commit()

        inserted = build_vocab_items_from_candidates(
            conn,
            source_name="sample_csv",
            truncate_topic_prefix="build:sample_csv",
        )
        assert inserted == 1

        rows = conn.execute(
            "SELECT lemma, topic_tag FROM vocab_items ORDER BY id"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["lemma"] == "janela"
        assert rows[0]["topic_tag"] == "build:sample_csv"
    finally:
        conn.close()
