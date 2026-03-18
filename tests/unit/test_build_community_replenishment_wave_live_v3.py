from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tools.build_community_replenishment_wave_live_v3 import load_scenarios, first_words


def test_first_words_basic() -> None:
    assert first_words("Как здесь правильно спросить, если нужно...", 2) == "как здесь"


def test_scenario_pack_v2_loads() -> None:
    scenarios = load_scenarios(Path("data/community_authoring/scenario_pack_v2.json"))
    assert len(scenarios) >= 12
    assert all(s.scenario_id for s in scenarios)
    assert all(s.question_forms for s in scenarios)


def test_minimal_db_contract(tmp_path: Path) -> None:
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
        ("Как мягко уточнить срок ответа?", "dialogue", "documents"),
    )
    conn.commit()
    row = conn.execute("SELECT COUNT(*) FROM community_content_items WHERE is_active = 1").fetchone()
    conn.close()
    assert row[0] == 1
