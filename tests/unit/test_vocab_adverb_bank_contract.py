
from __future__ import annotations
import sqlite3

DB_PATH = 'data/lingua_staging.db'

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def test_active_adverb_bank_has_no_duplicate_lemmas() -> None:
    conn = _conn()
    try:
        rows = conn.execute(
            '''
            SELECT LOWER(TRIM(lemma)) AS lemma_key, COUNT(*) AS n
            FROM vocab_items
            WHERE is_active = 1
              AND pos = 'adverb'
              AND topic_tag LIKE 'build:pilot_ptpt_%'
            GROUP BY LOWER(TRIM(lemma))
            HAVING COUNT(*) > 1
            '''
        ).fetchall()

        assert rows == []
    finally:
        conn.close()


def test_active_adverb_bank_not_empty() -> None:
    conn = _conn()
    try:
        row = conn.execute(
            '''
            SELECT COUNT(*) AS n
            FROM vocab_items
            WHERE is_active = 1
              AND pos = 'adverb'
              AND topic_tag LIKE 'build:pilot_ptpt_%'
            '''
        ).fetchone()

        assert row["n"] > 0
    finally:
        conn.close()


def test_active_adverb_bank_valid_choice_topology() -> None:
    conn = _conn()
    try:
        rows = conn.execute(
            '''
            SELECT
              i.id,
              COUNT(c.id) AS choice_count,
              SUM(CASE WHEN COALESCE(c.is_correct,0)=1 THEN 1 ELSE 0 END) AS correct_count
            FROM vocab_items i
            LEFT JOIN vocab_choices c ON c.item_id = i.id
            WHERE i.is_active = 1
              AND i.pos = 'adverb'
              AND i.topic_tag LIKE 'build:pilot_ptpt_%'
            GROUP BY i.id
            HAVING COUNT(c.id) <> 6
               OR SUM(CASE WHEN COALESCE(c.is_correct,0)=1 THEN 1 ELSE 0 END) <> 1
            '''
        ).fetchall()

        assert rows == []
    finally:
        conn.close()
