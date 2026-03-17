from __future__ import annotations

import sqlite3


_ALLOWED_POS = ("noun", "verb", "adjective", "adverb")
_TARGETS_24 = {
    "noun": 12,
    "verb": 4,
    "adjective": 4,
    "adverb": 4,
}


def _table_exists(conn: sqlite3.Connection, *, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, *, table: str, column: str) -> bool:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.DatabaseError:
        return False
    for row in rows:
        name = row[1] if isinstance(row, tuple) else row["name"]
        if name == column:
            return True
    return False


def _get_attempt_pos_counts(conn: sqlite3.Connection, attempt_id: int) -> dict[str, int]:
    if not _table_exists(conn, table="vocab_answers"):
        return {}
    if not _column_exists(conn, table="vocab_items", column="pos"):
        return {}

    rows = conn.execute(
        '''
        SELECT COALESCE(vi.pos, 'other') AS pos, COUNT(*) AS cnt
        FROM vocab_answers va
        JOIN vocab_items vi ON vi.id = va.item_id
        WHERE va.attempt_id = ?
        GROUP BY COALESCE(vi.pos, 'other')
        ''',
        (attempt_id,),
    ).fetchall()

    out: dict[str, int] = {}
    for row in rows:
        if isinstance(row, tuple):
            pos, cnt = row
        else:
            pos, cnt = row["pos"], row["cnt"]
        out[str(pos)] = int(cnt)
    return out


def remaining_targets_for_attempt(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    total_questions: int,
) -> dict[str, int]:
    observed = _get_attempt_pos_counts(conn, attempt_id)
    if total_questions != 24:
        return {k: max(0, 1 - observed.get(k, 0)) for k in _ALLOWED_POS}
    return {k: max(0, _TARGETS_24[k] - observed.get(k, 0)) for k in _ALLOWED_POS}


def coverage_priority_order(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    total_questions: int,
) -> list[str]:
    remaining = remaining_targets_for_attempt(
        conn,
        attempt_id=attempt_id,
        total_questions=total_questions,
    )
    ordered = sorted(_ALLOWED_POS, key=lambda p: (-remaining.get(p, 0), p))
    return [p for p in ordered if remaining.get(p, 0) > 0]


def get_attempt_coverage_snapshot(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    total_questions: int,
) -> dict:
    observed = _get_attempt_pos_counts(conn, attempt_id)
    remaining = remaining_targets_for_attempt(
        conn,
        attempt_id=attempt_id,
        total_questions=total_questions,
    )
    return {
        "attempt_id": attempt_id,
        "total_questions": total_questions,
        "observed_pos_counts": observed,
        "remaining_pos_targets": remaining,
        "priority_order": coverage_priority_order(
            conn,
            attempt_id=attempt_id,
            total_questions=total_questions,
        ),
    }
