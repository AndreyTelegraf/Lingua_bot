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


def _shift_bin(bin_name: str | None, delta: int) -> str | None:
    if not bin_name:
        return None
    raw = str(bin_name).strip().upper()
    if not raw.endswith("K"):
        return None
    try:
        n = int(raw[:-1])
    except ValueError:
        return None
    return f"{max(1, n + delta)}K"


def _load_recent_answer_signals(conn: sqlite3.Connection, *, attempt_id: int, limit: int = 2) -> list[dict[str, object]]:
    conn.row_factory = sqlite3.Row
    has_is_correct = _has_column(conn, table="vocab_attempt_events", column="is_correct")
    has_bin_name = _has_column(conn, table="vocab_items", column="bin_name")

    if not has_is_correct or not has_bin_name:
        return []

    rows = conn.execute(
        """
        SELECT
            vae.is_correct AS is_correct,
            vi.bin_name AS bin_name
        FROM vocab_attempt_events vae
        LEFT JOIN vocab_items vi ON vi.id = vae.item_id
        WHERE vae.attempt_id = ?
          AND vae.event_type = 'answer'
        ORDER BY vae.id DESC
        LIMIT ?
        """,
        (attempt_id, limit),
    ).fetchall()

    out: list[dict[str, object]] = []
    for row in rows:
        if row["is_correct"] is None:
            continue
        out.append(
            {
                "is_correct": 1 if int(row["is_correct"] or 0) == 1 else 0,
                "bin_name": row["bin_name"],
            }
        )
    return out


def _derive_target_bin(last_answers: list[dict[str, object]]) -> str | None:
    env_target_bin = os.getenv("VOCAB_TARGET_BIN")
    if env_target_bin:
        return env_target_bin

    if len(last_answers) < 2:
        return None

    latest_bin = last_answers[0].get("bin_name")
    if latest_bin is None:
        return None

    correct = sum(1 for row in last_answers[:2] if int(row.get("is_correct", 0) or 0) == 1)

    if correct == 2:
        return _shift_bin(str(latest_bin), 1)
    if correct == 0:
        return _shift_bin(str(latest_bin), -1)
    return str(latest_bin)


def _build_selector_sql(conn: sqlite3.Connection, *, apply_cooldown: bool, target_bin: str | None = None) -> tuple[str, tuple[object, ...]]:
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

    target_bin_order_sql = None
    target_bin_order_param = None
    if has_bin_name and target_bin:
        target_bin_order_sql = "CASE WHEN vi.bin_name = ? THEN 0 ELSE 1 END ASC"
        target_bin_order_param = target_bin
    elif has_bin_name:
        order_parts.append("CASE WHEN vi.bin_name IS NULL THEN 1 ELSE 0 END ASC")


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

    if target_bin_order_sql is not None:
        order_parts.insert(0, target_bin_order_sql)

    if _has_column(conn, table="vocab_items", column="freq_rank"):
        order_parts.extend(
            [
                "CASE WHEN vi.freq_rank IS NULL THEN 1 ELSE 0 END ASC",
                "vi.freq_rank ASC",
            ]
        )

    if target_bin_order_param is not None:
        params.append(target_bin_order_param)

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

    target_bin = _derive_target_bin(_load_recent_answer_signals(conn, attempt_id=attempt_id))

    sql_cooldown, base_params_cooldown = _build_selector_sql(conn, apply_cooldown=True, target_bin=target_bin)
    row = conn.execute(
        sql_cooldown.replace("{shown_filter_sql}", shown_filter_sql),
        (*base_params_cooldown, *shown_params),
    ).fetchone()
    if row is not None:
        return row

    sql_fallback, base_params_fallback = _build_selector_sql(conn, apply_cooldown=False, target_bin=target_bin)
    return conn.execute(
        sql_fallback.replace("{shown_filter_sql}", shown_filter_sql),
        (*base_params_fallback, *shown_params),
    ).fetchone()
