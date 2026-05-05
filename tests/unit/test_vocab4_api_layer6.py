from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services.vocab4 import api
from services.vocab4.exceptions import AttemptStateError

MIGRATION = Path("db/migrations_sqlite/020_vocab4_runtime.sql")


def _build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(MIGRATION.read_text(encoding="utf-8"))
    return conn


def _seed_item(
    conn: sqlite3.Connection,
    *,
    lemma: str,
    pos: str = "noun",
    bin_name: str = "1K",
    freq_rank: int | None = None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO vocab4_items
            (lemma, pos, bin_name, prompt, correct_choice, is_active, cert_status, freq_rank)
        VALUES (?, ?, ?, 'prompt', 'choice_0', 1, 'certified', ?)
        """,
        (lemma, pos, bin_name, freq_rank),
    )
    item_id = cursor.lastrowid
    for i in range(6):
        conn.execute(
            """
            INSERT INTO vocab4_choices (item_id, choice_text, is_correct, position_index)
            VALUES (?, ?, ?, ?)
            """,
            (item_id, f"choice_{i}", 1 if i == 0 else 0, i),
        )
    conn.commit()
    return item_id


# --- test 1 ---

def test_start_attempt_returns_attempt_id_and_item() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="casa", pos="noun", bin_name="1K")

    result = api.start_attempt(conn, user_id=1)

    assert "attempt_id" in result
    assert "item" in result
    assert isinstance(result["attempt_id"], int)
    assert result["item"]["pos"] == "noun"


# --- test 2 ---

def test_next_question_returns_new_item() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="a", pos="noun", bin_name="1K", freq_rank=1)
    _seed_item(conn, lemma="b", pos="noun", bin_name="1K", freq_rank=2)

    r = api.start_attempt(conn, user_id=1)
    first_id = r["item"]["id"]

    r2 = api.next_question(conn, r["attempt_id"])

    assert "item" in r2
    assert r2["item"]["id"] != first_id


# --- test 3 ---

def test_submit_answer_returns_in_progress_before_limit() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="a", pos="noun", bin_name="1K", freq_rank=1)
    _seed_item(conn, lemma="b", pos="noun", bin_name="1K", freq_rank=2)

    r = api.start_attempt(conn, user_id=1, question_limit=5)
    out = api.submit_answer(conn, r["attempt_id"], r["item"]["id"], None, 1)

    assert out["status"] == "in_progress"
    assert "next_step" in out
    assert "result" not in out


# --- test 4 ---

def test_submit_answer_returns_finished_with_result_at_limit() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="casa", pos="noun", bin_name="1K")

    r = api.start_attempt(conn, user_id=1, question_limit=1)
    out = api.submit_answer(conn, r["attempt_id"], r["item"]["id"], None, 1)

    assert out["status"] == "finished"
    assert "result" in out
    assert out["result"]["version"] == "vocab4_result_v1"
    assert out["result"]["signal_quality"] == "complete"


# --- test 5 ---

def test_finished_result_has_expected_counts() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="a", pos="noun", bin_name="1K", freq_rank=1)
    _seed_item(conn, lemma="b", pos="noun", bin_name="1K", freq_rank=2)

    r = api.start_attempt(conn, user_id=1, question_limit=2)
    attempt_id = r["attempt_id"]

    api.submit_answer(conn, attempt_id, r["item"]["id"], None, 1)   # correct
    item2 = api.next_question(conn, attempt_id)["item"]
    out = api.submit_answer(conn, attempt_id, item2["id"], None, 0)  # wrong

    result = out["result"]
    assert result["answered_count"] == 2
    assert result["correct_count"] == 1
    assert result["incorrect_count"] == 1
    assert result["accuracy"] == 0.5
    assert result["signal_quality"] == "complete"
    assert result["coverage"]["complete"] is True


# --- test 6 ---

def test_submit_after_finished_raises_AttemptStateError() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="casa", pos="noun", bin_name="1K")

    r = api.start_attempt(conn, user_id=1, question_limit=1)
    api.submit_answer(conn, r["attempt_id"], r["item"]["id"], None, 1)

    with pytest.raises(AttemptStateError):
        api.submit_answer(conn, r["attempt_id"], r["item"]["id"], None, 1)


# --- test 7 ---

def test_api_contains_no_sql_strings() -> None:
    source = Path("services/vocab4/api.py").read_text(encoding="utf-8")
    for kw in ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP"):
        assert kw not in source, f"SQL keyword {kw!r} found in api.py"


# --- test 8 ---

def test_api_does_not_import_selector() -> None:
    source = Path("services/vocab4/api.py").read_text(encoding="utf-8")
    assert "selector" not in source
