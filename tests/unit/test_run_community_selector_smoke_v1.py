from __future__ import annotations

import sqlite3
from pathlib import Path


def test_minimal_selector_contract(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE community_content_items (
            id INTEGER PRIMARY KEY,
            text TEXT NOT NULL,
            format_type TEXT NOT NULL,
            topic TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 100
        )
        """
    )
    conn.execute("INSERT INTO community_content_items (text, format_type, topic, is_active, priority) VALUES ('x', 'dialogue', 'housing', 1, 50)")
    conn.commit()

    row = conn.execute(
        "SELECT id, text FROM community_content_items WHERE is_active = 1 ORDER BY priority ASC, id ASC LIMIT 1"
    ).fetchone()
    conn.close()

    assert row is not None
    assert row[1] == "x"
