from __future__ import annotations

import json
import sqlite3

from services.vocab_bank.merge import (
    evaluate_candidate_eligibility,
    gloss_quality_score,
    merge_candidates_for_source,
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
    return conn


def test_gloss_quality_score_prefers_short_clean_gloss() -> None:
    a = gloss_quality_score("дом")
    b = gloss_quality_score("дом, жилище; место проживания")
    assert a > b


def test_evaluate_candidate_eligibility_smoke() -> None:
    conn = _prepare_conn()
    try:
        conn.execute(
            """
            INSERT INTO vocab_lemma_candidates (
                source_name, normalized_lemma, lemma_key, pos, level, freq_rank, ru_gloss, gloss_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sample", "casa", "casa", "noun", "A1", 300, "дом", "дом"),
        )
        row = conn.execute("SELECT * FROM vocab_lemma_candidates").fetchone()
        assert row is not None
        assert evaluate_candidate_eligibility(row) == (1, None)
    finally:
        conn.close()


def test_evaluate_candidate_eligibility_blocks_proper_and_religious_terms() -> None:
    conn = _prepare_conn()
    try:
        conn.executemany(
            """
            INSERT INTO vocab_lemma_candidates (
                source_name, normalized_lemma, lemma_key, pos, level, freq_rank, ru_gloss, gloss_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("sample", "lisboa", "lisboa", "noun", "A1", 1000, "лиссабон", "лиссабон"),
                ("sample", "igreja", "igreja", "noun", "A1", 900, "церковь", "церковь"),
                ("sample", "ônibus", "ônibus", "noun", "A1", 800, "автобус", "автобус"),
                ("sample", "machimbombo", "machimbombo", "noun", "A1", 800, "автобус", "автобус"),
            ],
        )
        rows = conn.execute("SELECT * FROM vocab_lemma_candidates ORDER BY id").fetchall()
        assert evaluate_candidate_eligibility(rows[0]) == (0, "blocked_proper_or_religious_term")
        assert evaluate_candidate_eligibility(rows[1]) == (0, "blocked_religious_or_archaic_term")
        assert evaluate_candidate_eligibility(rows[2]) == (0, "blocked_brazilianism")
        assert evaluate_candidate_eligibility(rows[3]) == (0, "blocked_africanism")
    finally:
        conn.close()


def test_merge_candidates_for_source_marks_duplicate_losers() -> None:
    conn = _prepare_conn()
    try:
        conn.executemany(
            """
            INSERT INTO vocab_lemma_candidates (
                source_name, normalized_lemma, lemma_key, pos, level, freq_rank, ru_gloss, gloss_key, is_eligible, reject_reason, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("sample_csv", "casa", "casa", "noun", "A1", 300, "дом", "дом", 1, None, "{}"),
                ("sample_csv", "casa", "casa", "noun", "A1", 310, "дом, жилище; место проживания", "дом, жилище; место проживания", 1, None, "{}"),
                ("sample_csv", "trabalhar", "trabalhar", "verb", "A1", 980, "работать", "работать", 1, None, "{}"),
            ],
        )
        conn.commit()

        affected = merge_candidates_for_source(conn, source_name="sample_csv")
        assert affected == 3

        rows = conn.execute(
            """
            SELECT normalized_lemma, pos, ru_gloss, is_eligible, reject_reason, merge_group_id, payload_json
            FROM vocab_lemma_candidates
            ORDER BY id
            """
        ).fetchall()

        assert rows[0]["is_eligible"] == 1
        assert rows[0]["reject_reason"] is None
        assert rows[1]["is_eligible"] == 0
        assert rows[1]["reject_reason"] == "duplicate_lemma_pos"
        assert rows[0]["merge_group_id"] == "casa::noun"
        assert rows[1]["merge_group_id"] == "casa::noun"

        payload = json.loads(rows[0]["payload_json"])
        assert payload["winner_id"] == 1
    finally:
        conn.close()


def test_merge_candidates_for_source_rejects_bad_pos() -> None:
    conn = _prepare_conn()
    try:
        conn.execute(
            """
            INSERT INTO vocab_lemma_candidates (
                source_name, normalized_lemma, lemma_key, pos, level, freq_rank, ru_gloss, gloss_key, is_eligible, reject_reason, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sample_jsonl", "lisboa", "lisboa", "proper_noun", "A1", 1000, "лиссабон", "лиссабон", 1, None, "{}"),
        )
        conn.commit()

        affected = merge_candidates_for_source(conn, source_name="sample_jsonl")
        assert affected == 1

        row = conn.execute(
            """
            SELECT is_eligible, reject_reason, merge_group_id
            FROM vocab_lemma_candidates
            WHERE normalized_lemma = 'lisboa'
            """
        ).fetchone()
        assert row is not None
        assert row["is_eligible"] == 0
        assert row["reject_reason"] == "unsupported_pos"
        assert row["merge_group_id"] == "lisboa::proper_noun"
    finally:
        conn.close()
