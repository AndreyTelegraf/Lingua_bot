from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path("/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")


def test_vocab_items_metadata_columns_exist() -> None:
    conn = sqlite3.connect(DB)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(vocab_items)")}
        assert {"lemma", "pos", "cefr_estimate", "concept_group"}.issubset(cols)
    finally:
        conn.close()


def test_vocab_items_activity_column_exists() -> None:
    conn = sqlite3.connect(DB)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(vocab_items)")}
        assert "is_active" in cols or "active" in cols
    finally:
        conn.close()
