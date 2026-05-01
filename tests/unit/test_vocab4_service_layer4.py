from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services.vocab4 import repo, service
from services.vocab4.exceptions import AttemptStateError, InsufficientBankError

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
        VALUES (?, ?, ?, 'Test prompt', 'answer', 1, 'certified', ?)
        """,
        (lemma, pos, bin_name, freq_rank),
    )
    conn.commit()
    return cursor.lastrowid


# --- test 1 ---

def test_start_new_attempt_creates_and_returns_first_question() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="casa", pos="noun", bin_name="1K")

    result = service.start_new_attempt(conn, user_id=1)

    assert "attempt_id" in result
    assert "item" in result
    assert result["item"]["pos"] == "noun"
    attempt = repo.load_attempt(conn, result["attempt_id"])
    assert attempt["status"] == "in_progress"


# --- test 2 ---

def test_start_new_attempt_rejects_if_active_attempt_exists() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="casa", pos="noun", bin_name="1K")

    service.start_new_attempt(conn, user_id=1)

    with pytest.raises(AttemptStateError):
        service.start_new_attempt(conn, user_id=1)


# --- test 3 ---

def test_get_next_question_advances_state() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="casa", pos="noun", bin_name="1K", freq_rank=1)
    _seed_item(conn, lemma="libro", pos="noun", bin_name="1K", freq_rank=2)

    start = service.start_new_attempt(conn, user_id=1)
    attempt_id = start["attempt_id"]
    first_id = start["item"]["id"]

    result = service.get_next_question(conn, attempt_id)
    assert result["item"]["id"] != first_id


# --- test 4 ---

def test_submit_answer_increments_step() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="casa", pos="noun", bin_name="1K")
    _seed_item(conn, lemma="libro", pos="noun", bin_name="1K")

    start = service.start_new_attempt(conn, user_id=1, question_limit=5)
    attempt_id = start["attempt_id"]
    item = start["item"]

    result = service.submit_answer(conn, attempt_id, item["id"], None, 1)

    assert result["status"] == "in_progress"
    assert result["next_step"] == 1


# --- test 5 ---

def test_submit_answer_finishes_at_limit() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="casa", pos="noun", bin_name="1K")

    start = service.start_new_attempt(conn, user_id=1, question_limit=1)
    attempt_id = start["attempt_id"]
    item = start["item"]

    result = service.submit_answer(conn, attempt_id, item["id"], None, 1)

    assert result["status"] == "finished"
    assert repo.load_attempt(conn, attempt_id)["status"] == "finished"


# --- test 6 ---

def test_submit_answer_rejects_if_not_in_progress() -> None:
    conn = _build_conn()
    attempt_id = repo.create_attempt(conn, user_id=1)
    conn.commit()
    # attempt is pending — never started

    with pytest.raises(AttemptStateError):
        service.submit_answer(conn, attempt_id, 1, None, 1)


# --- test 7 ---

def test_get_next_question_fails_if_pool_exhausted() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="casa", pos="noun", bin_name="1K")

    start = service.start_new_attempt(conn, user_id=1)
    # Only 1 item in pool; already shown — select_next must fail

    with pytest.raises(InsufficientBankError):
        service.get_next_question(conn, start["attempt_id"])


# --- test 8 ---

def test_full_3_step_flow() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="casa", pos="noun", bin_name="1K", freq_rank=1)
    _seed_item(conn, lemma="libro", pos="noun", bin_name="1K", freq_rank=2)
    _seed_item(conn, lemma="mesa", pos="noun", bin_name="1K", freq_rank=3)

    start = service.start_new_attempt(conn, user_id=1, question_limit=3)
    attempt_id = start["attempt_id"]
    item1 = start["item"]

    r1 = service.submit_answer(conn, attempt_id, item1["id"], None, 1)
    assert r1["status"] == "in_progress"
    assert r1["next_step"] == 1

    q2 = service.get_next_question(conn, attempt_id)
    item2 = q2["item"]
    assert item2["id"] != item1["id"]

    r2 = service.submit_answer(conn, attempt_id, item2["id"], None, 0)
    assert r2["status"] == "in_progress"
    assert r2["next_step"] == 2

    q3 = service.get_next_question(conn, attempt_id)
    item3 = q3["item"]
    assert item3["id"] not in {item1["id"], item2["id"]}

    r3 = service.submit_answer(conn, attempt_id, item3["id"], None, 1)
    assert r3["status"] == "finished"
    assert repo.load_attempt(conn, attempt_id)["status"] == "finished"
