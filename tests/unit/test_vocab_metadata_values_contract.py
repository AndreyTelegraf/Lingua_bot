from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path("/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")

VALID_POS = {
    "noun","verb","adjective","adverb",
    "pronoun","preposition","conjunction","interjection","expression","other"
}
VALID_CEFR = {"A0","A1","A2","B1","B2","C1","C2","unknown"}


def _activity_col(conn: sqlite3.Connection) -> str:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(vocab_items)")}
    if "is_active" in cols:
        return "is_active"
    if "active" in cols:
        return "active"
    raise AssertionError("No activity column found")


def test_active_vocab_metadata_has_valid_pos_and_cefr() -> None:
    conn = sqlite3.connect(DB)
    try:
        activity_col = _activity_col(conn)

        invalid_pos = conn.execute(f"""
            SELECT COUNT(*) FROM vocab_items
            WHERE {activity_col} = 1
              AND pos IS NOT NULL AND TRIM(pos) != ''
              AND pos NOT IN ({",".join(repr(x) for x in sorted(VALID_POS))})
        """).fetchone()[0]

        invalid_cefr = conn.execute(f"""
            SELECT COUNT(*) FROM vocab_items
            WHERE {activity_col} = 1
              AND cefr_estimate IS NOT NULL AND TRIM(cefr_estimate) != ''
              AND cefr_estimate NOT IN ({",".join(repr(x) for x in sorted(VALID_CEFR))})
        """).fetchone()[0]

        assert invalid_pos == 0
        assert invalid_cefr == 0
    finally:
        conn.close()


def test_active_vocab_metadata_has_no_concept_group_without_lemma() -> None:
    conn = sqlite3.connect(DB)
    try:
        activity_col = _activity_col(conn)
        bad = conn.execute(f"""
            SELECT COUNT(*) FROM vocab_items
            WHERE {activity_col} = 1
              AND concept_group IS NOT NULL AND TRIM(concept_group) != ''
              AND (lemma IS NULL OR TRIM(lemma) = '')
        """).fetchone()[0]
        assert bad == 0
    finally:
        conn.close()
