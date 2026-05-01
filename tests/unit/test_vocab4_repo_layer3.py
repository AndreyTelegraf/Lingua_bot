from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services.vocab4 import repo
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
    lemma: str = "casa",
    pos: str = "noun",
    bin_name: str = "1K",
    is_active: int = 1,
    cert_status: str = "certified",
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO vocab4_items
            (lemma, pos, bin_name, prompt, correct_choice, is_active, cert_status)
        VALUES (?, ?, ?, 'Test prompt', 'house', ?, ?)
        """,
        (lemma, pos, bin_name, is_active, cert_status),
    )
    return cursor.lastrowid


def _seed_choices(conn: sqlite3.Connection, item_id: int) -> None:
    for i in range(6):
        conn.execute(
            """
            INSERT INTO vocab4_choices (item_id, choice_text, is_correct, position_index)
            VALUES (?, ?, ?, ?)
            """,
            (item_id, f"choice_{i}", 1 if i == 0 else 0, i),
        )


# --- test 1 ---

def test_load_certified_pool_only_returns_active_certified() -> None:
    conn = _build_conn()
    _seed_item(conn, lemma="a", pos="noun", bin_name="1K", is_active=1, cert_status="certified")
    _seed_item(conn, lemma="b", pos="verb", bin_name="1K", is_active=1, cert_status="draft")
    _seed_item(conn, lemma="c", pos="adjective", bin_name="2K", is_active=0, cert_status="certified")
    conn.commit()

    pool = repo.load_certified_pool(conn)
    assert len(pool) == 1
    assert pool[0]["lemma"] == "a"


# --- test 2 ---

def test_load_certified_pool_includes_choices() -> None:
    conn = _build_conn()
    item_id = _seed_item(conn)
    _seed_choices(conn, item_id)
    conn.commit()

    pool = repo.load_certified_pool(conn)
    assert len(pool) == 1
    choices = pool[0]["choices"]
    assert len(choices) == 6
    assert [c["position_index"] for c in choices] == list(range(6))


# --- test 3 ---

def test_load_certified_pool_returns_empty_when_none() -> None:
    conn = _build_conn()
    assert repo.load_certified_pool(conn) == []


# --- test 4 ---

def test_create_attempt_returns_id_with_pending_status() -> None:
    conn = _build_conn()
    attempt_id = repo.create_attempt(conn, user_id=1)
    conn.commit()

    row = repo.load_attempt(conn, attempt_id)
    assert row is not None
    assert row["status"] == "pending"
    assert row["current_step"] == 0
    assert row["selector_state_json"] == "{}"
    assert row["question_limit"] == 24


# --- test 5 ---

def test_load_attempt_returns_none_for_missing_id() -> None:
    conn = _build_conn()
    assert repo.load_attempt(conn, 9999) is None


# --- test 6 ---

def test_start_attempt_transitions_to_in_progress() -> None:
    conn = _build_conn()
    attempt_id = repo.create_attempt(conn, user_id=1)
    conn.commit()

    repo.start_attempt(conn, attempt_id)
    conn.commit()

    assert repo.load_attempt(conn, attempt_id)["status"] == "in_progress"


# --- test 7 ---

def test_start_attempt_raises_if_not_pending() -> None:
    conn = _build_conn()
    attempt_id = repo.create_attempt(conn, user_id=1)
    conn.commit()
    repo.start_attempt(conn, attempt_id)
    conn.commit()

    with pytest.raises(AttemptStateError) as exc_info:
        repo.start_attempt(conn, attempt_id)
    assert exc_info.value.attempt_id == attempt_id


# --- test 8 ---

def test_persist_selector_state_updates_json() -> None:
    conn = _build_conn()
    attempt_id = repo.create_attempt(conn, user_id=1)
    conn.commit()
    repo.start_attempt(conn, attempt_id)
    conn.commit()

    repo.persist_selector_state(conn, attempt_id, '{"step":1}')
    conn.commit()

    assert repo.load_attempt(conn, attempt_id)["selector_state_json"] == '{"step":1}'


# --- test 9 ---

def test_record_answer_and_advance_writes_answer_and_step() -> None:
    conn = _build_conn()
    attempt_id = repo.create_attempt(conn, user_id=1)
    conn.commit()
    repo.start_attempt(conn, attempt_id)
    conn.commit()

    repo.record_answer_and_advance(
        conn, attempt_id, item_id=1, selected_choice_id=None, is_correct=1, new_step=1
    )

    assert repo.load_attempt(conn, attempt_id)["current_step"] == 1
    count = conn.execute(
        "SELECT COUNT(*) FROM vocab4_answers WHERE attempt_id = ?", (attempt_id,)
    ).fetchone()[0]
    assert count == 1


# --- test 10 ---

def test_record_answer_rejects_duplicate_attempt_item() -> None:
    conn = _build_conn()
    attempt_id = repo.create_attempt(conn, user_id=1)
    conn.commit()
    repo.start_attempt(conn, attempt_id)
    conn.commit()

    repo.record_answer_and_advance(
        conn, attempt_id, item_id=1, selected_choice_id=None, is_correct=1, new_step=1
    )
    with pytest.raises(sqlite3.IntegrityError):
        repo.record_answer_and_advance(
            conn, attempt_id, item_id=1, selected_choice_id=None, is_correct=0, new_step=2
        )


# --- test 11 ---

def test_finish_attempt_sets_status_and_finished_at() -> None:
    conn = _build_conn()
    attempt_id = repo.create_attempt(conn, user_id=1)
    conn.commit()
    repo.start_attempt(conn, attempt_id)
    conn.commit()

    repo.finish_attempt(conn, attempt_id)
    conn.commit()

    row = conn.execute(
        "SELECT status, finished_at FROM vocab4_attempts WHERE id = ?", (attempt_id,)
    ).fetchone()
    assert row["status"] == "finished"
    assert row["finished_at"] is not None


# --- test 12 ---

def test_full_sequence_create_start_persist_answer_finish() -> None:
    conn = _build_conn()

    attempt_id = repo.create_attempt(conn, user_id=1)
    conn.commit()
    assert repo.load_attempt(conn, attempt_id)["status"] == "pending"

    repo.start_attempt(conn, attempt_id)
    conn.commit()
    assert repo.load_attempt(conn, attempt_id)["status"] == "in_progress"

    repo.persist_selector_state(conn, attempt_id, '{"pos_used":{"noun":1}}')
    conn.commit()
    assert repo.load_attempt(conn, attempt_id)["selector_state_json"] == '{"pos_used":{"noun":1}}'

    repo.record_answer_and_advance(
        conn, attempt_id, item_id=42, selected_choice_id=None, is_correct=1, new_step=1
    )
    assert repo.load_attempt(conn, attempt_id)["current_step"] == 1

    repo.finish_attempt(conn, attempt_id)
    conn.commit()
    row = conn.execute(
        "SELECT status, finished_at FROM vocab4_attempts WHERE id = ?", (attempt_id,)
    ).fetchone()
    assert row["status"] == "finished"
    assert row["finished_at"] is not None


# --- test 13 (new) ---

def test_record_answer_rejects_non_in_progress_attempt_without_insert() -> None:
    conn = _build_conn()
    attempt_id = repo.create_attempt(conn, user_id=1)
    conn.commit()
    # attempt is 'pending' — never started

    with pytest.raises(AttemptStateError):
        repo.record_answer_and_advance(
            conn, attempt_id, item_id=1, selected_choice_id=None, is_correct=1, new_step=1
        )

    count = conn.execute(
        "SELECT COUNT(*) FROM vocab4_answers WHERE attempt_id = ?", (attempt_id,)
    ).fetchone()[0]
    assert count == 0
