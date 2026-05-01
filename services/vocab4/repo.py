from __future__ import annotations

import sqlite3
from typing import Any

from .exceptions import AttemptStateError


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def load_certified_pool(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    items = conn.execute(
        """
        SELECT id, lemma, pos, bin_name, cefr_hint, prompt, correct_choice,
               freq_rank, diagnostic_tags
        FROM vocab4_items
        WHERE is_active = 1 AND cert_status = 'certified'
        ORDER BY CASE WHEN freq_rank IS NULL THEN 1 ELSE 0 END,
                 freq_rank ASC,
                 id ASC
        """
    ).fetchall()

    if not items:
        return []

    choices_rows = conn.execute(
        """
        SELECT vc.id, vc.item_id, vc.choice_text, vc.is_correct, vc.position_index
        FROM vocab4_choices vc
        JOIN vocab4_items vi ON vi.id = vc.item_id
        WHERE vi.is_active = 1 AND vi.cert_status = 'certified'
        ORDER BY vc.item_id ASC, vc.position_index ASC
        """
    ).fetchall()

    choices_by_item: dict[int, list[dict]] = {}
    for c in choices_rows:
        d = _row_to_dict(c)
        choices_by_item.setdefault(d["item_id"], []).append(d)

    pool = []
    for row in items:
        item = _row_to_dict(row)
        item["choices"] = choices_by_item.get(item["id"], [])
        pool.append(item)

    return pool


def create_attempt(
    conn: sqlite3.Connection,
    user_id: int,
    question_limit: int = 24,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO vocab4_attempts (user_id, status, question_limit, selector_state_json)
        VALUES (?, 'pending', ?, '{}')
        """,
        (user_id, question_limit),
    )
    return cursor.lastrowid


def load_attempt(conn: sqlite3.Connection, attempt_id: int) -> dict | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT id, user_id, status, current_step, question_limit,
               selector_state_json, result_snapshot_json, created_at, updated_at
        FROM vocab4_attempts
        WHERE id = ?
        """,
        (attempt_id,),
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def load_active_attempt(conn: sqlite3.Connection, user_id: int) -> dict | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT id, user_id, status, current_step, question_limit,
               selector_state_json, result_snapshot_json
        FROM vocab4_attempts
        WHERE user_id = ? AND status = 'in_progress'
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def start_attempt(conn: sqlite3.Connection, attempt_id: int) -> None:
    cursor = conn.execute(
        """
        UPDATE vocab4_attempts
        SET status = 'in_progress', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'pending'
        """,
        (attempt_id,),
    )
    if cursor.rowcount == 0:
        raise AttemptStateError(attempt_id, "attempt is not in pending state")


def persist_selector_state(
    conn: sqlite3.Connection,
    attempt_id: int,
    state_json: str,
) -> None:
    cursor = conn.execute(
        """
        UPDATE vocab4_attempts
        SET selector_state_json = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'in_progress'
        """,
        (state_json, attempt_id),
    )
    if cursor.rowcount == 0:
        raise AttemptStateError(attempt_id, "attempt is not in_progress")


def record_answer_and_advance(
    conn: sqlite3.Connection,
    attempt_id: int,
    item_id: int,
    selected_choice_id: int | None,
    is_correct: int,
    new_step: int,
    *,
    answered_at: str | None = None,
) -> None:
    # Status guard first: if attempt is not in_progress, abort before any insert.
    cursor = conn.execute(
        """
        UPDATE vocab4_attempts
        SET current_step = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'in_progress'
        """,
        (new_step, attempt_id),
    )
    if cursor.rowcount == 0:
        conn.rollback()
        raise AttemptStateError(attempt_id, "attempt is not in_progress")
    try:
        conn.execute(
            """
            INSERT INTO vocab4_answers
                (attempt_id, item_id, selected_choice_id, is_correct, answered_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (attempt_id, item_id, selected_choice_id, is_correct, answered_at),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def finish_attempt(conn: sqlite3.Connection, attempt_id: int) -> None:
    cursor = conn.execute(
        """
        UPDATE vocab4_attempts
        SET status = 'finished',
            finished_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'in_progress'
        """,
        (attempt_id,),
    )
    if cursor.rowcount == 0:
        raise AttemptStateError(attempt_id, "attempt is not in_progress")


def abandon_attempt(conn: sqlite3.Connection, attempt_id: int) -> None:
    cursor = conn.execute(
        """
        UPDATE vocab4_attempts
        SET status = 'abandoned', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND status = 'in_progress'
        """,
        (attempt_id,),
    )
    if cursor.rowcount == 0:
        raise AttemptStateError(attempt_id, "attempt is not in_progress")
