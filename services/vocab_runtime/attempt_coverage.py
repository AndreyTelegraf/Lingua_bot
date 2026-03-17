from __future__ import annotations

import sqlite3

CORE_POS = ("noun", "verb", "adjective", "adverb")


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    for row in rows:
        name = row["name"] if isinstance(row, sqlite3.Row) else row[1]
        if name == column:
            return True
    return False


def _base_targets(total_questions: int) -> dict[str, int]:
    # Legacy contract for 24-question Vocab:
    # noun=12, verb=4, adjective=4, adverb=4
    # Scale conservatively for non-24 totals.
    if total_questions == 24:
        return {
            "noun": 12,
            "verb": 4,
            "adjective": 4,
            "adverb": 4,
        }

    noun = max(1, round(total_questions * 0.5))
    rem = max(0, total_questions - noun)
    verb = rem // 3
    adjective = rem // 3
    adverb = rem - verb - adjective
    return {
        "noun": noun,
        "verb": verb,
        "adjective": adjective,
        "adverb": adverb,
    }


def _observed_pos_counts(conn: sqlite3.Connection, *, attempt_id: int) -> dict[str, int]:
    if not _has_column(conn, "vocab_items", "pos"):
        return {}

    rows = conn.execute(
        '''
        SELECT COALESCE(NULLIF(TRIM(LOWER(vi.pos)), ''), 'other') AS pos, COUNT(*) AS cnt
        FROM vocab_answers va
        JOIN vocab_items vi ON vi.id = va.item_id
        WHERE va.attempt_id = ?
        GROUP BY COALESCE(NULLIF(TRIM(LOWER(vi.pos)), ''), 'other')
        ''',
        (attempt_id,),
    ).fetchall()

    out: dict[str, int] = {}
    for row in rows:
        pos = row["pos"] if isinstance(row, sqlite3.Row) else row[0]
        cnt = row["cnt"] if isinstance(row, sqlite3.Row) else row[1]
        out[str(pos)] = int(cnt)
    return out


def remaining_targets_for_attempt(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    total_questions: int,
) -> dict[str, int]:
    observed = _observed_pos_counts(conn, attempt_id=attempt_id)
    targets = _base_targets(total_questions)

    remaining: dict[str, int] = {}
    for pos in CORE_POS:
        remaining[pos] = max(0, int(targets[pos]) - int(observed.get(pos, 0) or 0))
    return remaining


def coverage_priority_order(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    total_questions: int,
) -> list[str]:
    observed = _observed_pos_counts(conn, attempt_id=attempt_id)
    remaining = remaining_targets_for_attempt(
        conn,
        attempt_id=attempt_id,
        total_questions=total_questions,
    )

    ranked: list[tuple[str, tuple[int, int, str]]] = []
    for pos in CORE_POS:
        rem_i = int(remaining.get(pos, 0) or 0)
        if rem_i <= 0:
            continue
        seen_i = int(observed.get(pos, 0) or 0)
        # Legacy order:
        # 1) bigger remaining gap first
        # 2) bigger observed count first (keeps noun-first behavior in old tests)
        # 3) stable lexical tie-break
        ranked.append((pos, (-rem_i, -seen_i, pos)))

    ranked.sort(key=lambda x: x[1])
    return [pos for pos, _ in ranked]


def get_attempt_coverage_snapshot(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    total_questions: int,
) -> dict:
    observed = _observed_pos_counts(conn, attempt_id=attempt_id)
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


def coverage_soft_bias_weights(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    total_questions: int,
    base_weight: float = 1.0,
    boost_per_missing_ratio: float = 1.0,
    unseen_bonus: float = 0.35,
) -> dict[str, float]:
    observed = _observed_pos_counts(conn, attempt_id=attempt_id)
    remaining = remaining_targets_for_attempt(
        conn,
        attempt_id=attempt_id,
        total_questions=total_questions,
    )
    targets = _base_targets(total_questions)

    out: dict[str, float] = {}
    for pos in CORE_POS:
        rem_i = int(remaining.get(pos, 0) or 0)
        seen_i = int(observed.get(pos, 0) or 0)
        target_i = max(1, int(targets.get(pos, 1) or 1))

        missing_ratio = rem_i / target_i
        weight = base_weight + missing_ratio * boost_per_missing_ratio

        if seen_i == 0 and rem_i > 0:
            weight += unseen_bonus

        out[pos] = round(weight, 4)
    return out
