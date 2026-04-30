from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

MIGRATION_PATH = Path("db/migrations_sqlite/020_vocab4_runtime.sql")

EXPECTED_TABLES = [
    "vocab4_items",
    "vocab4_choices",
    "vocab4_attempts",
    "vocab4_answers",
    "vocab4_events",
    "vocab4_results",
    "vocab4_authoring_items",
    "vocab4_certification_reviews",
]

FORBIDDEN_TOKENS = [
    "vocab_items",
    "vocab_choices",
    "vocab_attempts",
    "vocab_answers",
    "vocab_runtime",
    "vocab_v3",
    "vocab4_entries",
    "vocab4_tags",
    "vocab4_entry_tags",
]


def _fresh_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


# --- test 1 ---

def test_migration_applies_cleanly_and_all_tables_exist() -> None:
    conn = sqlite3.connect(":memory:")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    for table in EXPECTED_TABLES:
        assert table in tables, f"Expected table {table!r} not found after migration"


# --- test 2 ---

def test_migration_contains_no_legacy_tokens() -> None:
    sql = MIGRATION_PATH.read_text(encoding="utf-8")

    for token in FORBIDDEN_TOKENS:
        assert token not in sql, (
            f"Legacy token {token!r} found in 020_vocab4_runtime.sql"
        )


# --- test 3 ---

def test_vocab4_items_required_columns_exist() -> None:
    conn = _fresh_db()
    cols = _columns(conn, "vocab4_items")
    required = {
        "id", "lemma", "pos", "bin_name", "cefr_hint", "prompt",
        "correct_choice", "is_active", "cert_status", "diagnostic_tags", "created_at",
    }
    missing = required - cols
    assert not missing, f"vocab4_items missing columns: {missing}"


# --- test 4 ---

def test_vocab4_choices_required_columns_exist() -> None:
    conn = _fresh_db()
    cols = _columns(conn, "vocab4_choices")
    required = {"id", "item_id", "choice_text", "is_correct", "position_index"}
    missing = required - cols
    assert not missing, f"vocab4_choices missing columns: {missing}"


# --- test 5 ---

def test_vocab4_attempts_required_columns_exist() -> None:
    conn = _fresh_db()
    cols = _columns(conn, "vocab4_attempts")
    required = {
        "id", "user_id", "status", "question_limit", "current_step",
        "selector_state_json", "result_snapshot_json", "created_at", "updated_at",
    }
    missing = required - cols
    assert not missing, f"vocab4_attempts missing columns: {missing}"


# --- test 6 ---

def test_vocab4_items_safe_defaults() -> None:
    conn = _fresh_db()
    conn.execute(
        "INSERT INTO vocab4_items (lemma, pos, bin_name, prompt, correct_choice)"
        " VALUES ('casa', 'noun', '1K', 'What is casa?', 'house')"
    )
    row = conn.execute(
        "SELECT is_active, cert_status FROM vocab4_items WHERE lemma = 'casa'"
    ).fetchone()
    assert row[0] == 0, f"is_active default must be 0, got {row[0]}"
    assert row[1] == "draft", f"cert_status default must be 'draft', got {row[1]!r}"


# --- test 7 ---

def test_check_constraints_reject_invalid_values() -> None:
    conn = _fresh_db()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO vocab4_items (lemma, pos, bin_name, prompt, correct_choice)"
            " VALUES ('a', 'pronoun', '1K', 'q', 'a')"
        )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO vocab4_items (lemma, pos, bin_name, prompt, correct_choice)"
            " VALUES ('b', 'noun', '3K', 'q', 'a')"
        )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO vocab4_items"
            " (lemma, pos, bin_name, prompt, correct_choice, cert_status)"
            " VALUES ('c', 'noun', '1K', 'q', 'a', 'approved')"
        )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO vocab4_choices (item_id, choice_text, is_correct, position_index)"
            " VALUES (1, 'text', 2, 0)"
        )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO vocab4_choices (item_id, choice_text, is_correct, position_index)"
            " VALUES (1, 'text', 0, 6)"
        )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO vocab4_attempts (user_id, status)"
            " VALUES (1, 'active')"
        )


# --- test 8 ---

def test_uniqueness_constraints() -> None:
    conn = _fresh_db()

    conn.execute(
        "INSERT INTO vocab4_items (lemma, pos, bin_name, prompt, correct_choice)"
        " VALUES ('casa', 'noun', '1K', 'q', 'a')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO vocab4_items (lemma, pos, bin_name, prompt, correct_choice)"
            " VALUES ('casa', 'noun', '1K', 'q2', 'a2')"
        )

    conn.execute(
        "INSERT INTO vocab4_choices (item_id, choice_text, is_correct, position_index)"
        " VALUES (1, 'house', 1, 0)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO vocab4_choices (item_id, choice_text, is_correct, position_index)"
            " VALUES (1, 'home', 0, 0)"
        )

    conn.execute(
        "INSERT INTO vocab4_answers (attempt_id, item_id, is_correct)"
        " VALUES (1, 1, 1)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO vocab4_answers (attempt_id, item_id, is_correct)"
            " VALUES (1, 1, 0)"
        )


# --- test 9 ---

def test_critical_indexes_exist() -> None:
    conn = _fresh_db()
    indexes = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    for name in (
        "idx_vocab4_items_active_cert",
        "idx_vocab4_choices_item_id",
        "idx_vocab4_attempts_user_status",
        "idx_vocab4_answers_attempt_id",
    ):
        assert name in indexes, f"Expected index {name!r} not found"


# --- test 10 ---

def test_migration_idempotent() -> None:
    conn = sqlite3.connect(":memory:")
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.executescript(sql)
