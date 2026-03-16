from __future__ import annotations

import os
import sqlite3
import json


_DEFAULT_POS_TARGET_SHARE = {
    "noun": 0.40,
    "verb": 0.25,
    "adjective": 0.20,
    "adverb": 0.15,
}


def rebalance_pos_weights(
    base_weights: dict[str, float],
    pos_counters: dict[str, int],
    *,
    asked_count: int,
) -> dict[str, float]:
    """
    Soft POS balancing for 24-question vocab attempts.

    Goals:
    - nouns can dominate, but not completely
    - verbs must not disappear
    - underrepresented POS get progressive boost
    """
    if not base_weights:
        return {}

    out: dict[str, float] = {}
    total_asked = max(asked_count, 0)

    for pos, base in base_weights.items():
        current = int(pos_counters.get(pos, 0))
        target_share = _DEFAULT_POS_TARGET_SHARE.get(pos, 0.10)
        target_count = target_share * max(total_asked, 1)

        # shortage > 0 means this POS is under target
        shortage = max(target_count - current, 0.0)
        overshoot = max(current - target_count, 0.0)

        boost = 1.0 + (shortage * 0.65)
        penalty = max(0.20, 1.0 - (overshoot * 0.18))

        # hard anti-starvation rule for verbs and adjectives
        if total_asked >= 8 and pos == "verb" and current == 0:
            boost = max(boost, 4.0)
        elif total_asked >= 12 and pos == "verb" and current <= 1:
            boost = max(boost, 3.0)
        elif total_asked >= 10 and pos == "adjective" and current == 0:
            boost = max(boost, 2.5)
        elif total_asked >= 12 and pos == "adverb" and current == 0:
            boost = max(boost, 2.0)

        out[pos] = float(base) * boost * penalty

    return out


_SHOWN_EVENT_TYPES = ("shown", "question_shown")


def _selector_trace_enabled() -> bool:
    return os.getenv("VOCAB_SELECTOR_TRACE", "").strip().lower() in {"1", "true", "yes", "on"}


def _trace_selector(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    step: int,
    preferred_pos_order: list[str],
    chosen_row: sqlite3.Row | None,
    chosen_source: str,
) -> None:
    if not _selector_trace_enabled():
        return
    try:
        payload = {
            "attempt_id": attempt_id,
            "step": step,
            "preferred_pos_order": preferred_pos_order,
            "chosen_source": chosen_source,
            "chosen_item_id": None if chosen_row is None else chosen_row["id"],
            "chosen_lemma": None if chosen_row is None else chosen_row["lemma"],
            "chosen_pos": None if chosen_row is None else chosen_row["pos"],
            "chosen_bin_name": None if chosen_row is None else chosen_row["bin_name"] if "bin_name" in chosen_row.keys() else None,
            "chosen_freq_rank": None if chosen_row is None else chosen_row["freq_rank"] if "freq_rank" in chosen_row.keys() else None,
        }
        print("VOCAB_SELECTOR_TRACE " + json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        print(f"VOCAB_SELECTOR_TRACE_FAILED: {exc}")

# POS balancing helper inserted below.


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


def _load_attempt_pos_counts(conn: sqlite3.Connection, *, attempt_id: int) -> dict[str, int]:
    conn.row_factory = sqlite3.Row
    placeholders = ", ".join("?" for _ in _SHOWN_EVENT_TYPES)
    rows = conn.execute(
        f'''
        SELECT vi.pos AS pos, COUNT(*) AS n
        FROM vocab_attempt_events vae
        JOIN vocab_items vi ON vi.id = vae.item_id
        WHERE vae.attempt_id = ?
          AND vae.event_type IN ({placeholders})
          AND vi.pos IS NOT NULL
        GROUP BY vi.pos
        ''',
        (attempt_id, *_SHOWN_EVENT_TYPES),
    ).fetchall()
    return {str(row["pos"]): int(row["n"] or 0) for row in rows}


def _load_available_pos_counts(
    conn: sqlite3.Connection,
    *,
    soft_start_bins: tuple[str, ...] | None = None,
) -> dict[str, int]:
    conn.row_factory = sqlite3.Row
    where_parts = ["is_active = 1", "pos IS NOT NULL"]
    params: list[object] = []
    if _has_column(conn, table="vocab_items", column="bin_name") and soft_start_bins:
        placeholders = ", ".join("?" for _ in soft_start_bins)
        where_parts.append(f"bin_name IN ({placeholders})")
        params.extend(list(soft_start_bins))
    sql = f'''
        SELECT pos, COUNT(*) AS n
        FROM vocab_items
        WHERE {" AND ".join(where_parts)}
        GROUP BY pos
    '''
    rows = conn.execute(sql, tuple(params)).fetchall()
    return {str(row["pos"]): int(row["n"] or 0) for row in rows}


def _preferred_pos_order(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    asked_count: int,
    soft_start_bins: tuple[str, ...] | None = None,
) -> list[str]:
    available = _load_available_pos_counts(conn, soft_start_bins=soft_start_bins)
    if not available:
        return []

    pos_counters = _load_attempt_pos_counts(conn, attempt_id=attempt_id)
    base_weights = {pos: 1.0 for pos in available}
    weights = rebalance_pos_weights(base_weights, pos_counters, asked_count=asked_count)

    def sort_key(pos: str) -> tuple[float, int, int, str]:
        return (
            -float(weights.get(pos, 0.0)),
            int(pos_counters.get(pos, 0)),
            -int(available.get(pos, 0)),
            pos,
        )

    return sorted(available.keys(), key=sort_key)


def _build_selector_sql(
    conn: sqlite3.Connection,
    *,
    apply_cooldown: bool,
    target_bin: str | None = None,
    soft_start_bins: tuple[str, ...] | None = None,
    required_pos: str | None = None,
) -> tuple[str, tuple[object, ...], tuple[object, ...]]:
    select_cols = "vi.id, vi.lemma, vi.question_text, vi.correct_answer, vi.pos"
    join_sql = ""
    where_parts = [
        "vi.is_active = 1",
    ]
    order_parts: list[str] = []
    params_before_shown: list[object] = []
    params_after_shown: list[object] = []

    has_exposure = (
        _table_exists(conn, table="vocab_item_exposure")
        and _has_column(conn, table="vocab_item_exposure", column="item_id")
        and _has_column(conn, table="vocab_item_exposure", column="shown_count")
    )
    has_last_shown_at = has_exposure and _has_column(conn, table="vocab_item_exposure", column="last_shown_at")
    has_bin_name = _has_column(conn, table="vocab_items", column="bin_name")

    if has_bin_name and soft_start_bins:
        placeholders = ", ".join("?" for _ in soft_start_bins)
        where_parts.append(f"vi.bin_name IN ({placeholders})")
        params_before_shown.extend(list(soft_start_bins))

    if required_pos:
        where_parts.append("vi.pos = ?")
        params_before_shown.append(required_pos)

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
        params_before_shown.append(cooldown_sec)

    if has_bin_name and target_bin:
        order_parts.insert(0, "CASE WHEN vi.bin_name = ? THEN 0 ELSE 1 END ASC")
        params_after_shown.append(target_bin)
    elif has_bin_name and not has_exposure:
        order_parts.append(
            "CASE vi.bin_name "
            "WHEN '1K' THEN 1 "
            "WHEN '2K' THEN 2 "
            "WHEN '5K' THEN 3 "
            "WHEN '10K' THEN 4 "
            "WHEN '20K' THEN 5 "
            "ELSE 99 END ASC"
        )
    elif has_bin_name:
        order_parts.append("CASE WHEN vi.bin_name IS NULL THEN 1 ELSE 0 END ASC")

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
    return sql, tuple(params_before_shown), tuple(params_after_shown)


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

    step_row = conn.execute(
        f"""
        SELECT COUNT(*) AS n
        FROM vocab_attempt_events
        WHERE attempt_id = ?
          AND event_type IN ({placeholders})
        """,
        shown_params,
    ).fetchone()
    step = int(step_row["n"] or 0) if step_row is not None else 0

    soft_start_bins: tuple[str, ...] | None = ("1K", "2K") if step < 6 else None
    target_bin = _derive_target_bin(_load_recent_answer_signals(conn, attempt_id=attempt_id))
    preferred_pos_order = _preferred_pos_order(
        conn,
        attempt_id=attempt_id,
        asked_count=step,
        soft_start_bins=soft_start_bins,
    )

    for required_pos in preferred_pos_order:
        sql_cooldown, before_cooldown, after_cooldown = _build_selector_sql(
            conn,
            apply_cooldown=True,
            target_bin=target_bin,
            soft_start_bins=soft_start_bins,
            required_pos=required_pos,
        )
        row = conn.execute(
            sql_cooldown.replace("{shown_filter_sql}", shown_filter_sql),
            (*before_cooldown, *shown_params, *after_cooldown),
        ).fetchone()
        if row is not None:
            _trace_selector(
                conn,
                attempt_id=attempt_id,
                step=step,
                preferred_pos_order=preferred_pos_order,
                chosen_row=row,
                chosen_source=f"cooldown_required_pos:{required_pos}",
            )
            return row

    sql_cooldown, before_cooldown, after_cooldown = _build_selector_sql(
        conn,
        apply_cooldown=True,
        target_bin=target_bin,
        soft_start_bins=soft_start_bins,
        required_pos=None,
    )
    row = conn.execute(
        sql_cooldown.replace("{shown_filter_sql}", shown_filter_sql),
        (*before_cooldown, *shown_params, *after_cooldown),
    ).fetchone()
    if row is not None:
        _trace_selector(
            conn,
            attempt_id=attempt_id,
            step=step,
            preferred_pos_order=preferred_pos_order,
            chosen_row=row,
            chosen_source="cooldown_no_required_pos",
        )
        return row

    for required_pos in preferred_pos_order:
        sql_fallback, before_fallback, after_fallback = _build_selector_sql(
            conn,
            apply_cooldown=False,
            target_bin=target_bin,
            soft_start_bins=soft_start_bins,
            required_pos=required_pos,
        )
        row = conn.execute(
            sql_fallback.replace("{shown_filter_sql}", shown_filter_sql),
            (*before_fallback, *shown_params, *after_fallback),
        ).fetchone()
        if row is not None:
            return row

    sql_fallback, before_fallback, after_fallback = _build_selector_sql(
        conn,
        apply_cooldown=False,
        target_bin=target_bin,
        soft_start_bins=soft_start_bins,
        required_pos=None,
    )
    row = conn.execute(
        sql_fallback.replace("{shown_filter_sql}", shown_filter_sql),
        (*before_fallback, *shown_params, *after_fallback),
    ).fetchone()
    _trace_selector(
        conn,
        attempt_id=attempt_id,
        step=step,
        preferred_pos_order=preferred_pos_order,
        chosen_row=row,
        chosen_source="fallback_no_required_pos",
    )
    return row
