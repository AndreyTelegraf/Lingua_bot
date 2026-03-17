from __future__ import annotations

import sqlite3

from services.vocab_runtime.progression_export import build_vocab_progression_export


def test_progression_export_contract_shape() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE vocab_attempts (
            id INTEGER PRIMARY KEY,
            status TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE vocab_answers (
            id INTEGER PRIMARY KEY,
            attempt_id INTEGER,
            item_id INTEGER,
            is_correct INTEGER DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE vocab_items (
            id INTEGER PRIMARY KEY,
            is_active INTEGER,
            lemma TEXT,
            pos TEXT,
            cefr_estimate TEXT,
            concept_group TEXT,
            freq_rank INTEGER,
            correct_answer TEXT
        )
        """
    )
    conn.execute("INSERT INTO vocab_attempts(id, status) VALUES (1, 'finished')")
    conn.execute(
        """
        INSERT INTO vocab_items(id, is_active, lemma, pos, cefr_estimate, concept_group, freq_rank, correct_answer)
        VALUES (10, 1, 'casa', 'noun', 'A1', 'house_home', 100, 'дом')
        """
    )
    conn.execute("INSERT INTO vocab_answers(attempt_id, item_id, is_correct) VALUES (1, 10, 1)")

    out = build_vocab_progression_export(conn, attempt_id=1)
    assert out["mode"] == "vocab"
    assert out["spec_version"] == "progression_export_v1"
    assert out["attempt_id"] == 1
    assert "profile" in out
