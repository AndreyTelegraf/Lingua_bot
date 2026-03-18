from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tools.apply_community_review_to_staging_v1 import load_review_rows


def test_load_review_rows(tmp_path: Path) -> None:
    p = tmp_path / "x.tsv"
    p.write_text(
        "scenario_id\ttopic\tformat_type\topening_family\tcontext\tintent\treview_action\treview_note\ttext\n"
        "s1\thousing\tdialogue\topen\tctx\tgoal\tkeep\t\ttext 1\n",
        encoding="utf-8",
    )
    rows = load_review_rows(p)
    assert len(rows) == 1
    assert rows[0].scenario_id == "s1"
    assert rows[0].review_action == "keep"


def test_insert_contract_columns_exist(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE community_content_items (
            id INTEGER PRIMARY KEY,
            text TEXT NOT NULL,
            format_type TEXT NOT NULL,
            topic TEXT,
            region TEXT,
            has_question INTEGER NOT NULL DEFAULT 0,
            difficulty TEXT NOT NULL DEFAULT 'light',
            is_active INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(community_content_items)").fetchall()]
    conn.close()

    assert "text" in cols
    assert "format_type" in cols
    assert "topic" in cols
    assert "region" in cols
    assert "has_question" in cols
    assert "difficulty" in cols
    assert "is_active" in cols
    assert "priority" in cols
