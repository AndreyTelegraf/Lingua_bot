from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services.vocab4.authoring import EXPECTED_COLUMNS, import_authoring_csv_text
from services.vocab4.certification import (
    load_pending_authoring_items,
    promote_authoring_item,
    reject_authoring_item,
)

MIGRATION = Path("db/migrations_sqlite/020_vocab4_runtime.sql")

_HEADER  = ",".join(EXPECTED_COLUMNS)
_ROW_1   = "casa,noun,1K,What does this mean?,house,home,building,place,structure,dwelling,test_source,author1"
_ROW_2   = "libro,noun,1K,What does this mean?,book,page,text,object,notebook,volume,test_source,author1"
_ROW_DUP = "casa,noun,1K,A different prompt?,castle,palace,mansion,cottage,villa,lodge,test_source2,auth2"


def _build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(MIGRATION.read_text(encoding="utf-8"))
    return conn


def _csv(*data_rows: str) -> str:
    return "\n".join([_HEADER] + list(data_rows))


def _seed(conn: sqlite3.Connection, *rows: str) -> list[int]:
    before = {r[0] for r in conn.execute("SELECT id FROM vocab4_authoring_items").fetchall()}
    import_authoring_csv_text(conn, _csv(*rows), dry_run=False)
    after = conn.execute(
        "SELECT id FROM vocab4_authoring_items ORDER BY id ASC"
    ).fetchall()
    return [r[0] for r in after if r[0] not in before]


# --- test 1 ---

def test_load_pending_authoring_items_returns_only_pending() -> None:
    conn = _build_conn()
    ids = _seed(conn, _ROW_1, _ROW_2)
    conn.execute("UPDATE vocab4_authoring_items SET cert_status='rejected' WHERE id=?", (ids[0],))
    conn.commit()

    result = load_pending_authoring_items(conn)

    assert len(result) == 1
    assert result[0]["cert_status"] == "pending"
    assert result[0]["lemma"] == "libro"
    assert result[0]["id"] == ids[1]


# --- test 2 ---

def test_reject_authoring_item_marks_rejected_and_touches_no_runtime_tables() -> None:
    conn = _build_conn()
    (auth_id,) = _seed(conn, _ROW_1)

    reject_authoring_item(conn, auth_id, reason="too easy", reviewer_notes="reject note")

    row = conn.execute("SELECT * FROM vocab4_authoring_items WHERE id=?", (auth_id,)).fetchone()
    assert row["cert_status"] == "rejected"
    assert row["reject_reason"] == "too easy"
    assert row["reviewer_notes"] == "reject note"
    assert conn.execute("SELECT COUNT(*) FROM vocab4_items").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM vocab4_choices").fetchone()[0] == 0


# --- test 3 ---

def test_promote_authoring_item_creates_runtime_item() -> None:
    conn = _build_conn()
    (auth_id,) = _seed(conn, _ROW_1)

    item_id = promote_authoring_item(conn, auth_id)

    assert isinstance(item_id, int)
    row = conn.execute("SELECT * FROM vocab4_items WHERE id=?", (item_id,)).fetchone()
    assert row["lemma"] == "casa"
    assert row["pos"] == "noun"
    assert row["bin_name"] == "1K"
    assert row["is_active"] == 1
    assert row["cert_status"] == "certified"
    assert row["prompt"] == "What does this mean?"
    assert row["correct_choice"] == "house"


# --- test 4 ---

def test_promote_authoring_item_creates_exactly_6_choices() -> None:
    conn = _build_conn()
    (auth_id,) = _seed(conn, _ROW_1)

    item_id = promote_authoring_item(conn, auth_id)

    choices = conn.execute(
        "SELECT * FROM vocab4_choices WHERE item_id=? ORDER BY position_index", (item_id,)
    ).fetchall()
    assert len(choices) == 6
    assert [c["position_index"] for c in choices] == list(range(6))


# --- test 5 ---

def test_promote_authoring_item_sets_exactly_one_correct_choice() -> None:
    conn = _build_conn()
    (auth_id,) = _seed(conn, _ROW_1)

    item_id = promote_authoring_item(conn, auth_id)

    choices = conn.execute(
        "SELECT * FROM vocab4_choices WHERE item_id=? ORDER BY position_index", (item_id,)
    ).fetchall()
    correct = [c for c in choices if c["is_correct"] == 1]
    assert len(correct) == 1
    assert correct[0]["position_index"] == 0
    assert correct[0]["choice_text"] == "house"
    wrong = [c for c in choices if c["is_correct"] == 0]
    assert len(wrong) == 5
    assert all(c["position_index"] > 0 for c in wrong)


# --- test 6 ---

def test_promote_authoring_item_marks_authoring_certified_with_promoted_item_id() -> None:
    conn = _build_conn()
    (auth_id,) = _seed(conn, _ROW_1)

    item_id = promote_authoring_item(conn, auth_id, reviewer_notes="looks good")

    auth_row = conn.execute(
        "SELECT * FROM vocab4_authoring_items WHERE id=?", (auth_id,)
    ).fetchone()
    assert auth_row["cert_status"] == "certified"
    assert auth_row["promoted_item_id"] == item_id
    assert auth_row["reviewer_notes"] == "looks good"


# --- test 7 ---

def test_promote_missing_authoring_item_raises() -> None:
    conn = _build_conn()

    with pytest.raises(ValueError, match="not found"):
        promote_authoring_item(conn, 9999)

    assert conn.execute("SELECT COUNT(*) FROM vocab4_items").fetchone()[0] == 0


# --- test 8 ---

def test_promote_rejected_authoring_item_raises_and_rolls_back() -> None:
    conn = _build_conn()
    (auth_id,) = _seed(conn, _ROW_1)
    conn.execute("UPDATE vocab4_authoring_items SET cert_status='rejected' WHERE id=?", (auth_id,))
    conn.commit()

    with pytest.raises(ValueError):
        promote_authoring_item(conn, auth_id)

    assert conn.execute("SELECT COUNT(*) FROM vocab4_items").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM vocab4_choices").fetchone()[0] == 0
    auth = conn.execute(
        "SELECT cert_status FROM vocab4_authoring_items WHERE id=?", (auth_id,)
    ).fetchone()
    assert auth["cert_status"] == "rejected"


# --- test 9 ---

def test_promote_duplicate_runtime_item_rolls_back_authoring_status() -> None:
    conn = _build_conn()
    id1, id2 = _seed(conn, _ROW_1, _ROW_DUP)

    promote_authoring_item(conn, id1)

    with pytest.raises(Exception):
        promote_authoring_item(conn, id2)

    auth2 = conn.execute(
        "SELECT cert_status, promoted_item_id FROM vocab4_authoring_items WHERE id=?", (id2,)
    ).fetchone()
    assert auth2["cert_status"] == "pending"
    assert auth2["promoted_item_id"] is None
    assert conn.execute("SELECT COUNT(*) FROM vocab4_items").fetchone()[0] == 1


# --- test 10 ---

def test_certification_does_not_touch_attempt_answer_event_result_tables() -> None:
    conn = _build_conn()
    id1, id2 = _seed(conn, _ROW_1, _ROW_2)

    promote_authoring_item(conn, id1)
    reject_authoring_item(conn, id2, reason="too easy")

    for table in ("vocab4_attempts", "vocab4_answers", "vocab4_events", "vocab4_results"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert count == 0, f"{table} was written by certification"


# --- test 11 ---

def test_certification_module_has_no_selector_service_api_result_imports() -> None:
    source = Path("services/vocab4/certification.py").read_text(encoding="utf-8")
    import_lines = [
        line.strip() for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    for forbidden in ("selector", "service", "api", "result", "authoring"):
        assert not any(forbidden in line for line in import_lines), (
            f"forbidden import {forbidden!r} found in certification.py"
        )
