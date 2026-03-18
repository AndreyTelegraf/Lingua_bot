from __future__ import annotations

import sqlite3

from services.community_block.content_registry import (
    export_seed_bank,
    fingerprint_text,
    import_candidates,
    normalize_text,
)


def build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE community_content_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            format_type TEXT NOT NULL,
            topic TEXT,
            region TEXT,
            has_question INTEGER NOT NULL DEFAULT 1,
            difficulty TEXT NOT NULL DEFAULT 'light',
            is_active INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 50,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    return conn


def test_normalize_and_fingerprint_collapse_cosmetic_differences() -> None:
    a = "  Как бы вы мягко сказали продавцу, что цена уже слегка из параллельной вселенной? "
    b = "Как бы вы мягко сказали продавцу что цена уже слегка из параллельной вселенной"
    assert normalize_text(a) == normalize_text(b)
    assert fingerprint_text(a) == fingerprint_text(b)


def test_import_candidates_rejects_existing_and_batch_duplicates() -> None:
    conn = build_conn()
    conn.execute(
        """
        INSERT INTO community_content_items(text, format_type, topic, region, has_question, difficulty, is_active, priority)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Как бы вы мягко сказали продавцу, что цена уже слегка из параллельной вселенной?",
            "nuance",
            "financas",
            None,
            1,
            "light",
            1,
            50,
        ),
    )
    conn.commit()

    result = import_candidates(
        conn,
        items=[
            {
                "text": "Как бы вы мягко сказали продавцу что цена уже слегка из параллельной вселенной",
                "format_type": "nuance",
                "topic": "financas",
            },
            {
                "text": "Чем в живой речи чаще заменяют formalíssimo habitação когда говорят про съём?",
                "format_type": "local",
                "topic": "housing",
            },
            {
                "text": "Чем в живой речи чаще заменяют formalíssimo habitação когда говорят про съём",
                "format_type": "local",
                "topic": "housing",
            },
        ],
    )

    assert result["inserted_count"] == 1
    assert result["rejected_existing_count"] == 1
    assert result["rejected_batch_count"] == 1
    count = conn.execute("SELECT COUNT(*) FROM community_content_items").fetchone()[0]
    assert count == 2


def test_export_seed_bank_writes_jsonl(tmp_path) -> None:
    conn = build_conn()
    conn.execute(
        """
        INSERT INTO community_content_items(text, format_type, topic, region, has_question, difficulty, is_active, priority)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("Тестовый текст", "nuance", "financas", None, 1, "light", 1, 50),
    )
    conn.commit()

    out = tmp_path / "seed.jsonl"
    export_seed_bank(conn, output_path=out)

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert '"fingerprint":' in lines[0]
