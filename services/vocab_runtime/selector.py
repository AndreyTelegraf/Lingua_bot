from __future__ import annotations

import os
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


def _cooldown_sec() -> int:
    raw = os.getenv("VOCAB_RUNTIME_ITEM_COOLDOWN_SEC", "86400").strip()
    try:
        value = int(raw)
    except ValueError:
        return 86400
    return max(0, value)


def _build_selector_sql(conn: sqlite3.Connection, *, apply_cooldown: bool) -> tuple[str, tuple[object, ...]]:
    select_cols = "vi.id, vi.lemma, vi.question_text, vi.correct_answer, vi.pos"
    join_sql = ""
    where_parts = [
        "vi.is_active = 1",
    ]
    order_parts: list[str] = []
    params: list[object] = []

    has_exposure = (
        _table_exists(conn, table="vocab_item_exposure")
        and _has_column(conn, table="vocab_item_exposure", column="item_id")
        and _has_column(conn, table="vocab_item_exposure", column="shown_count")
    )
    has_last_shown_at = has_exposure and _has_column(conn, table="vocab_item_exposure", column="last_shown_at")
    has_bin_name = _has_column(conn, table="vocab_items", column="bin_name")

    if has_exposure:
        select_cols += ", COALESCE(vie.shown_count, 0) AS global_shown_count"
        join_sql = "LEFT JOIN vocab_item_exposure vie ON vie.item_id = vi.id"

    if has_exposure and has_bin_name:
        select_cols += (
            ", COALESCE(( "
            "SELECT AVG(COALESCE(vie2.shown_count, 0)) "
            "FROM vocab_items vi2 "
            "LEFT JOIN vocab_item_exposure vie2 ON vie2.item_id = vi2.id "
            "WHERE vi2.is_active = 1 "
            "AND ( "
            "(vi.bin_name IS NULL AND vi2.bin_name IS NULL) "
            "OR vi2.bin_name = vi.bin_name "
            ") "
            "), 0) AS bin_exposure_avg"
        )
        order_parts.append("bin_exposure_avg ASC")

    if has_exposure:
        order_parts.append("COALESCE(vie.shown_count, 0) ASC")

    cooldown_sec = _cooldown_sec()
    if apply_cooldown and has_last_shown_at and cooldown_sec > 0:
        where_parts.append(
            "(vie.last_shown_at IS NULL OR vie.last_shown_at <= datetime('now', '-' || ? || ' seconds'))"
        )
        params.append(cooldown_sec)

    if _has_column(conn, table="vocab_items", column="freq_rank"):
        order_parts.extend(
            [
                "CASE WHEN vi.freq_rank IS NULL THEN 1 ELSE 0 END ASC",
                "vi.freq_rank ASC",
            ]
        )

    order_parts.append("vi.id ASC")
    order_sql = "ORDER BY " + ", ".join(order_parts)
    where_sql = " AND ".join(where_parts)

    sql = f"""
        SELECT {select_cols}
        FROM vocab_items vi
        {join_sql}
        WHERE {where_sql}
        {{shown_filter_sql}}
        {order_sql}
        LIMIT 1
    """
    return sql, tuple(params)


def get_next_item(conn: sqlite3.Connection, *, attempt_id: int) -> sqlite3.Row | None:
    conn.row_factory = sqlite3.Row

    placeholders = ", ".join("?" for _ in _SHOWN_EVENT_TYPES)
    shown_filter_sql = f"""
      AND vi.id NOT IN (
        SELECT item_id
        FROM vocab_attempt_events
        WHERE attempt_id = ?
          AND event_type IN ({placeholders})
      )
    """

    shown_params = (attempt_id, *_SHOWN_EVENT_TYPES)

    sql_cooldown, base_params_cooldown = _build_selector_sql(conn, apply_cooldown=True)
    row = conn.execute(
        sql_cooldown.replace("{shown_filter_sql}", shown_filter_sql),
        (*base_params_cooldown, *shown_params),
    ).fetchone()
    if row is not None:
        return row

    sql_fallback, base_params_fallback = _build_selector_sql(conn, apply_cooldown=False)
    return conn.execute(
        sql_fallback.replace("{shown_filter_sql}", shown_filter_sql),
        (*base_params_fallback, *shown_params),
    ).fetchone()
