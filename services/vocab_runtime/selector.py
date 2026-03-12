from __future__ import annotations

import sqlite3


_SHOWN_EVENT_TYPES = ("shown", "question_shown")


def _table_exists(conn: sqlite3.Connection, *, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _has_column(conn: sqlite3.Connection, *, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    for row in rows:
        name = row[1] if not isinstance(row, sqlite3.Row) else row["name"]
        if str(name) == column:
            return True
    return False


def get_next_item(conn: sqlite3.Connection, *, attempt_id: int) -> sqlite3.Row | None:
    conn.row_factory = sqlite3.Row

    select_cols = "vi.id, vi.lemma, vi.question_text, vi.correct_answer, vi.pos"
    join_sql = ""
    order_parts: list[str] = []

    has_exposure = (
        _table_exists(conn, table="vocab_item_exposure")
        and _has_column(conn, table="vocab_item_exposure", column="item_id")
        and _has_column(conn, table="vocab_item_exposure", column="shown_count")
    )
    if has_exposure:
        select_cols += ", COALESCE(vie.shown_count, 0) AS global_shown_count"
        join_sql = "LEFT JOIN vocab_item_exposure vie ON vie.item_id = vi.id"
        order_parts.append("COALESCE(vie.shown_count, 0) ASC")

    if _has_column(conn, table="vocab_items", column="freq_rank"):
        order_parts.extend(
            [
                "CASE WHEN vi.freq_rank IS NULL THEN 1 ELSE 0 END ASC",
                "vi.freq_rank ASC",
            ]
        )

    order_parts.append("vi.id ASC")
    order_sql = "ORDER BY " + ", ".join(order_parts)

    placeholders = ", ".join("?" for _ in _SHOWN_EVENT_TYPES)
    sql = f'''
        SELECT {select_cols}
        FROM vocab_items vi
        {join_sql}
        WHERE vi.is_active = 1
          AND vi.id NOT IN (
            SELECT item_id
            FROM vocab_attempt_events
            WHERE attempt_id = ?
              AND event_type IN ({placeholders})
          )
        {order_sql}
        LIMIT 1
    '''

    params = (attempt_id, *_SHOWN_EVENT_TYPES)
    return conn.execute(sql, params).fetchone()
