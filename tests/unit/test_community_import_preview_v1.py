from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tools.build_community_import_preview_v1 import load_schema, load_review_rows


def test_load_review_rows(tmp_path: Path) -> None:
    p = tmp_path / "x.tsv"
    p.write_text(
        "scenario_id\ttopic\tformat_type\topening_family\tcontext\tintent\treview_action\treview_note\ttext\n"
        "s1\thousing\tdialogue\tЧто обычно говорят, когда\tctx\tgoal\tkeep\t\ttext 1\n",
        encoding="utf-8",
    )
    rows = load_review_rows(p)
    assert len(rows) == 1
    assert rows[0]["scenario_id"] == "s1"


def test_load_schema(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE community_content_items (id INTEGER PRIMARY KEY, topic TEXT, format_type TEXT, text TEXT)")
    conn.commit()
    conn.close()

    cols = load_schema(db, "community_content_items")
    names = [c["name"] for c in cols]
    assert "topic" in names
    assert "format_type" in names
    assert "text" in names
