from __future__ import annotations

import sqlite3

from services.vocab_bank.build_choices import build_vocab_choices_for_items


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
    return conn


def test_build_vocab_choices_smoke_same_pos_only() -> None:
    conn = _prepare_conn()
    try:
        rows = [
            ("casa", "casa", "дом", "noun", "A1", 300, "1K", "build:sample_csv", 0),
            ("janela", "janela", "окно", "noun", "A2", 1700, "2K", "build:sample_jsonl", 0),
            ("estrada", "estrada", "дорога", "noun", "B1", 3200, "5K", "build:sample_csv", 0),
            ("livro", "livro", "книга", "noun", "A1", 500, "1K", "build:sample_csv", 0),
            ("água", "água", "вода", "noun", "A1", 600, "1K", "build:sample_csv", 0),
            ("mesa", "mesa", "стол", "noun", "A1", 700, "1K", "build:sample_csv", 0),
            ("trabalhar", "trabalhar", "работать", "verb", "A1", 980, "1K", "build:sample_csv", 0),
            ("escolher", "escolher", "выбирать", "verb", "B1", 3600, "5K", "build:sample_jsonl", 0),
            ("cedo", "cedo", "рано", "adverb", "A2", 2600, "5K", "build:sample_csv", 0),
            ("talvez", "talvez", "возможно", "adverb", "B1", 4700, "5K", "build:sample_csv", 0),
        ]
        conn.executemany(
            """
            INSERT INTO vocab_items (
                lemma, question_text, correct_answer, pos, level, freq_rank, bin_name, topic_tag, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

        built = build_vocab_choices_for_items(
            conn,
            topic_tag_prefix="build:",
            truncate_existing=True,
        )
        assert built == 6

        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM vocab_choices
            WHERE item_id = 1
            """
        ).fetchone()
        assert row is not None
        assert int(row["n"]) == 6

        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM vocab_choices
            WHERE item_id = 1 AND is_correct = 1
            """
        ).fetchone()
        assert row is not None
        assert int(row["n"]) == 1

        positions = conn.execute(
            """
            SELECT item_id, position_index
            FROM vocab_choices
            WHERE is_correct = 1
            ORDER BY item_id
            """
        ).fetchall()
        assert len(positions) == 6
        assert any(int(r["position_index"]) != 1 for r in positions)

        built_item_ids = conn.execute(
            "SELECT DISTINCT item_id FROM vocab_choices ORDER BY item_id"
        ).fetchall()
        assert [int(r[0]) for r in built_item_ids] == [1, 2, 3, 4, 5, 6]
    finally:
        conn.close()


def test_build_vocab_choices_skips_when_same_pos_pool_too_small() -> None:
    conn = _prepare_conn()
    try:
        rows = [
            ("casa", "casa", "дом", "noun", "A1", 300, "1K", "build:sample_csv", 0),
            ("janela", "janela", "окно", "noun", "A2", 1700, "2K", "build:sample_jsonl", 0),
            ("trabalhar", "trabalhar", "работать", "verb", "A1", 980, "1K", "build:sample_csv", 0),
        ]
        conn.executemany(
            """
            INSERT INTO vocab_items (
                lemma, question_text, correct_answer, pos, level, freq_rank, bin_name, topic_tag, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

        built = build_vocab_choices_for_items(
            conn,
            topic_tag_prefix="build:",
            truncate_existing=True,
        )
        assert built == 0
    finally:
        conn.close()
