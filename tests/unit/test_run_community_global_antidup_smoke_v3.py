from __future__ import annotations

import sqlite3
from pathlib import Path


def test_global_antidup_minimal_contract(tmp_path: Path) -> None:
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
    conn.execute(
        "INSERT INTO community_content_items (text, format_type, topic, is_active, priority) VALUES (?, ?, ?, 1, 50)",
        ("Как здесь правильно спросить, если нужен статус?", "dialogue", "documents"),
    )
    conn.commit()
    row = conn.execute("SELECT COUNT(*) FROM community_content_items WHERE is_active = 1").fetchone()
    conn.close()
    assert row[0] == 1
