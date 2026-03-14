from __future__ import annotations

import sqlite3


DB_PATH = "data/lingua_staging.db"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def test_active_vocab_items_have_exactly_6_choices() -> None:
    conn = _conn()
    try:
        rows = conn.execute(
            '''
            SELECT
              i.id,
              i.lemma,
              i.pos,
              i.bin_name,
              COUNT(c.id) AS choice_count
            FROM vocab_items i
            LEFT JOIN vocab_choices c ON c.item_id = i.id
            WHERE COALESCE(i.is_active, 1) = 1
            GROUP BY i.id, i.lemma, i.pos, i.bin_name
            HAVING COUNT(c.id) <> 6
            ORDER BY i.id
            '''
        ).fetchall()

        assert rows == [], [
            {
                "id": int(r["id"]),
                "lemma": str(r["lemma"]),
                "pos": str(r["pos"]) if r["pos"] is not None else None,
                "bin_name": str(r["bin_name"]) if r["bin_name"] is not None else None,
                "choice_count": int(r["choice_count"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def test_active_vocab_items_have_exactly_one_correct_choice() -> None:
    conn = _conn()
    try:
        rows = conn.execute(
            '''
            SELECT
              i.id,
              i.lemma,
              i.pos,
              i.bin_name,
              SUM(CASE WHEN COALESCE(c.is_correct, 0) = 1 THEN 1 ELSE 0 END) AS correct_count
            FROM vocab_items i
            LEFT JOIN vocab_choices c ON c.item_id = i.id
            WHERE COALESCE(i.is_active, 1) = 1
            GROUP BY i.id, i.lemma, i.pos, i.bin_name
            HAVING SUM(CASE WHEN COALESCE(c.is_correct, 0) = 1 THEN 1 ELSE 0 END) <> 1
            ORDER BY i.id
            '''
        ).fetchall()

        assert rows == [], [
            {
                "id": int(r["id"]),
                "lemma": str(r["lemma"]),
                "pos": str(r["pos"]) if r["pos"] is not None else None,
                "bin_name": str(r["bin_name"]) if r["bin_name"] is not None else None,
                "correct_count": int(r["correct_count"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def test_active_vocab_items_have_no_duplicate_lemmas() -> None:
    conn = _conn()
    try:
        rows = conn.execute(
            '''
            SELECT
              LOWER(TRIM(lemma)) AS lemma_key,
              COUNT(*) AS n
            FROM vocab_items
            WHERE COALESCE(is_active, 1) = 1
            GROUP BY LOWER(TRIM(lemma))
            HAVING COUNT(*) > 1
            ORDER BY n DESC, lemma_key
            '''
        ).fetchall()

        assert rows == [], [
            {
                "lemma": str(r["lemma_key"]),
                "n": int(r["n"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def test_vocab_choices_have_no_orphans() -> None:
    conn = _conn()
    try:
        rows = conn.execute(
            '''
            SELECT
              c.id,
              c.item_id,
              c.choice_text,
              c.is_correct,
              c.position_index
            FROM vocab_choices c
            LEFT JOIN vocab_items i ON i.id = c.item_id
            WHERE i.id IS NULL
            ORDER BY c.id
            '''
        ).fetchall()

        assert rows == [], [
            {
                "choice_id": int(r["id"]),
                "item_id": int(r["item_id"]) if r["item_id"] is not None else None,
                "choice_text": str(r["choice_text"]),
                "is_correct": int(r["is_correct"]),
                "position_index": int(r["position_index"]),
            }
            for r in rows
        ]
    finally:
        conn.close()
