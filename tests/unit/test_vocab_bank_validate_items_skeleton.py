from __future__ import annotations

import sqlite3

from services.vocab_bank.validate_items import validate_and_publish_items


def _prepare_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute(
        """
        CREATE TABLE vocab_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma TEXT NOT NULL,
            question_text TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            pos TEXT,
            level TEXT,
            freq_rank INTEGER,
            bin_name TEXT,
            topic_tag TEXT,
            is_active INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE vocab_choices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            choice_text TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            position_index INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE vocab_builds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            build_code TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            target_size INTEGER,
            source_snapshot_json TEXT NOT NULL DEFAULT '{}',
            config_json TEXT NOT NULL DEFAULT '{}',
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE vocab_item_validation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            build_id INTEGER NOT NULL,
            item_temp_id TEXT,
            rule_code TEXT NOT NULL,
            severity TEXT NOT NULL,
            passed INTEGER NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def test_validate_and_publish_items_smoke() -> None:
    conn = _prepare_conn()
    try:
        conn.execute(
            """
            INSERT INTO vocab_items (
                lemma, question_text, correct_answer, pos, level, freq_rank, bin_name, topic_tag, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("casa", "casa", "дом", "noun", "A1", 300, "1K", "build:sample", 0),
        )
        conn.executemany(
            """
            INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index)
            VALUES (?, ?, ?, ?)
            """,
            [
                (1, "дом", 1, 1),
                (1, "окно", 0, 2),
                (1, "дорога", 0, 3),
                (1, "книга", 0, 4),
                (1, "вода", 0, 5),
                (1, "работать", 0, 6),
            ],
        )
        conn.commit()

        published = validate_and_publish_items(
            conn,
            topic_tag_prefix="build:sample",
            build_code="test_build_ok",
            publish=True,
        )
        assert published == 1

        row = conn.execute("SELECT is_active FROM vocab_items WHERE id = 1").fetchone()
        assert row is not None
        assert int(row["is_active"]) == 1

        row = conn.execute("SELECT COUNT(*) AS n FROM vocab_item_validation").fetchone()
        assert row is not None
        assert int(row["n"]) >= 6
    finally:
        conn.close()


def test_validate_and_publish_items_rejects_bad_item() -> None:
    conn = _prepare_conn()
    try:
        conn.execute(
            """
            INSERT INTO vocab_items (
                lemma, question_text, correct_answer, pos, level, freq_rank, bin_name, topic_tag, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("casa", "casa", "дом", "noun", "A1", 300, "1K", "build:sample", 0),
        )
        conn.executemany(
            """
            INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index)
            VALUES (?, ?, ?, ?)
            """,
            [
                (1, "дом", 1, 1),
                (1, "дом", 0, 2),
                (1, "дорога", 0, 3),
            ],
        )
        conn.commit()

        published = validate_and_publish_items(
            conn,
            topic_tag_prefix="build:sample",
            build_code="test_build_bad",
            publish=True,
        )
        assert published == 0

        row = conn.execute("SELECT is_active FROM vocab_items WHERE id = 1").fetchone()
        assert row is not None
        assert int(row["is_active"]) == 0
    finally:
        conn.close()
