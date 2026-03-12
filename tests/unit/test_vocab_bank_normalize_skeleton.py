from __future__ import annotations

import json
import sqlite3

from services.vocab_bank.normalize import (
    build_candidate_from_raw_row,
    make_gloss_key,
    make_lemma_key,
    normalize_gloss,
    normalize_lemma,
    normalize_raw_entries_to_candidates,
)


def _prepare_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute(
        """
        CREATE TABLE vocab_raw_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            external_key TEXT,
            raw_lemma TEXT,
            raw_pos TEXT,
            raw_level TEXT,
            raw_freq TEXT,
            raw_gloss_ru TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

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


def test_normalize_lemma_smoke() -> None:
    assert normalize_lemma("  Casa  ") == "casa"
    assert normalize_lemma("«Trabalhar»") == "trabalhar"
    assert normalize_lemma(None) is None


def test_normalize_gloss_smoke() -> None:
    assert normalize_gloss("  [rare] дом ") == "дом"
    assert normalize_gloss("to work") == "work"
    assert normalize_gloss(None) is None


def test_keys_smoke() -> None:
    assert make_lemma_key("casa") == "casa"
    assert make_gloss_key("Дом") == "дом"


def test_build_candidate_from_raw_row_smoke() -> None:
    conn = _prepare_conn()
    try:
        conn.execute(
            """
            INSERT INTO vocab_raw_entries (
                source_name, raw_lemma, raw_pos, raw_level, raw_freq, raw_gloss_ru, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("sample_csv", " Casa ", "noun", "A1", "300", " [rare] дом ", "{}"),
        )
        row = conn.execute("SELECT * FROM vocab_raw_entries").fetchone()
        assert row is not None

        candidate = build_candidate_from_raw_row(row)
        assert candidate.normalized_lemma == "casa"
        assert candidate.lemma_key == "casa"
        assert candidate.ru_gloss == "дом"
        assert candidate.gloss_key == "дом"
        assert candidate.freq_rank == 300
        assert candidate.is_eligible == 1

        payload = json.loads(candidate.payload_json)
        assert payload["source_name"] == "sample_csv"
    finally:
        conn.close()


def test_normalize_raw_entries_to_candidates_smoke() -> None:
    conn = _prepare_conn()
    try:
        conn.executemany(
            """
            INSERT INTO vocab_raw_entries (
                source_name, raw_lemma, raw_pos, raw_level, raw_freq, raw_gloss_ru, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("sample_csv", " Casa ", "noun", "A1", "300", " дом ", "{}"),
                ("sample_csv", " Trabalhar ", "verb", "A1", "980", " работать ", "{}"),
                ("sample_jsonl", "", "noun", "A2", "1000", " окно ", "{}"),
            ],
        )
        conn.commit()

        inserted = normalize_raw_entries_to_candidates(
            conn,
            truncate_source=False,
        )
        assert inserted == 3

        rows = conn.execute(
            """
            SELECT source_name, normalized_lemma, lemma_key, pos, level, freq_rank, ru_gloss, gloss_key, is_eligible, reject_reason
            FROM vocab_lemma_candidates
            ORDER BY id
            """
        ).fetchall()

        assert len(rows) == 3
        assert rows[0]["normalized_lemma"] == "casa"
        assert rows[0]["ru_gloss"] == "дом"
        assert rows[1]["freq_rank"] == 980
        assert rows[2]["is_eligible"] == 0
        assert rows[2]["reject_reason"] == "missing_lemma"
    finally:
        conn.close()


def test_normalize_raw_entries_to_candidates_truncate_source() -> None:
    conn = _prepare_conn()
    try:
        conn.executemany(
            """
            INSERT INTO vocab_raw_entries (
                source_name, raw_lemma, raw_pos, raw_level, raw_freq, raw_gloss_ru, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("sample_csv", " Casa ", "noun", "A1", "300", " дом ", "{}"),
                ("sample_csv", " Trabalhar ", "verb", "A1", "980", " работать ", "{}"),
            ],
        )
        conn.commit()

        inserted1 = normalize_raw_entries_to_candidates(conn, source_name="sample_csv", truncate_source=False)
        inserted2 = normalize_raw_entries_to_candidates(conn, source_name="sample_csv", truncate_source=True)

        assert inserted1 == 2
        assert inserted2 == 2

        n = conn.execute(
            "SELECT COUNT(*) FROM vocab_lemma_candidates WHERE source_name = 'sample_csv'"
        ).fetchone()[0]
        assert n == 2
    finally:
        conn.close()
