from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from services.vocab4.authoring import (
    EXPECTED_COLUMNS,
    import_authoring_csv_text,
    validate_authoring_csv_text,
)

MIGRATION = Path("db/migrations_sqlite/020_vocab4_runtime.sql")

_VALID_ROW_1 = (
    "casa,noun,1K,What does this mean?,"
    "house,home,building,place,structure,dwelling,"
    "test_source,author1"
)
_VALID_ROW_2 = (
    "libro,noun,1K,What does this mean?,"
    "book,page,text,object,notebook,volume,"
    "test_source,author1"
)

_HEADER = ",".join(EXPECTED_COLUMNS)


def _build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(MIGRATION.read_text(encoding="utf-8"))
    return conn


def _csv(*data_rows: str, header: bool = True) -> str:
    lines = ([_HEADER] if header else []) + list(data_rows)
    return "\n".join(lines)


# --- test 1 ---

def test_valid_csv_passes_validation() -> None:
    result = validate_authoring_csv_text(_csv(_VALID_ROW_1))

    assert result["ok"] is True
    assert result["rows_total"] == 1
    assert result["valid_rows"] == 1
    assert result["errors"] == []


# --- test 2 ---

def test_invalid_header_fails() -> None:
    csv_text = "lemma,pos,bin_name,prompt\ncasa,noun,1K,test"
    result = validate_authoring_csv_text(csv_text)

    assert result["ok"] is False
    assert result["rows_total"] == 0
    assert any(e["code"] == "bad_header" for e in result["errors"])


# --- test 3 ---

def test_bad_pos_fails() -> None:
    row = "casa,NOUN,1K,prompt,house,home,building,place,structure,dwelling,src,auth"
    result = validate_authoring_csv_text(_csv(row))

    assert result["ok"] is False
    assert result["valid_rows"] == 0
    assert result["errors"][0]["code"] == "bad_pos"
    assert result["errors"][0]["row"] == 1


# --- test 4 ---

def test_bad_bin_fails() -> None:
    row = "casa,noun,3K,prompt,house,home,building,place,structure,dwelling,src,auth"
    result = validate_authoring_csv_text(_csv(row))

    assert result["ok"] is False
    assert any(e["code"] == "bad_bin_name" for e in result["errors"])


# --- test 5 ---

def test_empty_required_fields_fail() -> None:
    # lemma="" and prompt="" in the same row
    row = ",noun,1K,,house,home,building,place,structure,dwelling,src,auth"
    result = validate_authoring_csv_text(_csv(row))

    codes = [e["code"] for e in result["errors"]]
    assert "empty_lemma" in codes
    assert "empty_prompt" in codes
    assert result["ok"] is False
    assert result["valid_rows"] == 0


# --- test 6 ---

def test_duplicate_choices_fail_case_insensitive() -> None:
    # correct_choice="House", distractor_1="house" — collision after lower()
    row = "casa,noun,1K,prompt,House,house,building,place,structure,dwelling,src,auth"
    result = validate_authoring_csv_text(_csv(row))

    assert result["ok"] is False
    assert any(e["code"] == "duplicate_choice" for e in result["errors"])


# --- test 7 ---

def test_dry_run_writes_nothing() -> None:
    conn = _build_conn()
    result = import_authoring_csv_text(conn, _csv(_VALID_ROW_1), dry_run=True)

    assert result["ok"] is True
    assert result["import_count"] == 0
    count = conn.execute("SELECT COUNT(*) FROM vocab4_authoring_items").fetchone()[0]
    assert count == 0


# --- test 8 ---

def test_failed_validation_writes_nothing_even_when_dry_run_false() -> None:
    conn = _build_conn()
    row = "casa,BADPOS,1K,prompt,house,home,building,place,structure,dwelling,src,auth"
    result = import_authoring_csv_text(conn, _csv(row), dry_run=False)

    assert result["ok"] is False
    assert result["import_count"] == 0
    count = conn.execute("SELECT COUNT(*) FROM vocab4_authoring_items").fetchone()[0]
    assert count == 0


# --- test 9 ---

def test_import_writes_only_authoring_items() -> None:
    conn = _build_conn()
    result = import_authoring_csv_text(
        conn, _csv(_VALID_ROW_1, _VALID_ROW_2), dry_run=False, author_user_id=99
    )

    assert result["ok"] is True
    assert result["import_count"] == 2
    assert conn.execute("SELECT COUNT(*) FROM vocab4_authoring_items").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM vocab4_items").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM vocab4_choices").fetchone()[0] == 0


# --- test 10 ---

def test_import_payload_contains_normalized_choices() -> None:
    conn = _build_conn()
    import_authoring_csv_text(conn, _csv(_VALID_ROW_1), dry_run=False)

    row = conn.execute(
        "SELECT payload_json, distractors_json FROM vocab4_authoring_items LIMIT 1"
    ).fetchone()

    payload = json.loads(row["payload_json"])
    assert "choices" in payload
    assert len(payload["choices"]) == 6
    assert payload["choices"][0] == "house"
    assert "home" in payload["choices"]

    distractors = json.loads(row["distractors_json"])
    assert len(distractors) == 5
    assert "home" in distractors
    assert "house" not in distractors


# --- test 11 ---

def test_import_never_touches_runtime_tables() -> None:
    conn = _build_conn()
    import_authoring_csv_text(conn, _csv(_VALID_ROW_1), dry_run=False)

    for table in (
        "vocab4_items",
        "vocab4_choices",
        "vocab4_attempts",
        "vocab4_answers",
        "vocab4_events",
        "vocab4_results",
    ):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count == 0, f"{table} was written by authoring import"
