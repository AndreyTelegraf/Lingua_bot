from __future__ import annotations

import json
import sqlite3
from typing import Any


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


def _json_dumps(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _format_accuracy_pct(correct: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((correct / total) * 100.0, 1)


def _band_midpoint(bin_name: str | None) -> int | None:
    if not bin_name:
        return None
    raw = str(bin_name).strip().upper()
    if raw.endswith("K"):
        try:
            n = int(raw[:-1])
        except ValueError:
            return None
        low = max((n - 1) * 1000 + 1, 1)
        high = n * 1000
        return (low + high) // 2
    return None


def _row_get(row: sqlite3.Row | None, key: str, default: object = None) -> object:
    if row is None:
        return default
    if key not in row.keys():
        return default
    return row[key]


def _estimate_vocab_metrics(conn: sqlite3.Connection, *, attempt_id: int, correct: int, total: int) -> dict[str, object]:
    if total <= 0:
        return {
            "estimated_vocab_size": None,
            "estimated_vocab_band": "insufficient_data",
            "confidence": 0.0,
            "scoring_model": "runtime_scoring_v1",
            "coverage_score": 0.0,
            "difficulty_score": 0.0,
            "spread_score": 0.0,
            "sample_score": 0.0,
            "weighted_bin_hits": {},
        }

    conn.row_factory = sqlite3.Row

    has_bin_name = _has_column(conn, table="vocab_items", column="bin_name")
    has_freq_rank = _has_column(conn, table="vocab_items", column="freq_rank")

    select_bits = [
        "vae.is_correct AS is_correct",
    ]
    if has_bin_name:
        select_bits.append("vi.bin_name AS bin_name")
    else:
        select_bits.append("NULL AS bin_name")
    if has_freq_rank:
        select_bits.append("vi.freq_rank AS freq_rank")
    else:
        select_bits.append("NULL AS freq_rank")

    sql = f"""
        SELECT {", ".join(select_bits)}
        FROM vocab_attempt_events vae
        LEFT JOIN vocab_items vi ON vi.id = vae.item_id
        WHERE vae.attempt_id = ?
          AND vae.event_type = 'answer'
        ORDER BY vae.id ASC
    """
    rows = conn.execute(sql, (attempt_id,)).fetchall()

    weighted_hits: dict[str, float] = {}
    weighted_correct_sum = 0.0
    weighted_total_sum = 0.0
    freq_points: list[int] = []
    bin_seen: set[str] = set()

    for row in rows:
        is_correct = 1 if int(_row_get(row, "is_correct", 0) or 0) == 1 else 0
        bin_name = _row_get(row, "bin_name")
        freq_rank = _row_get(row, "freq_rank")

        midpoint = None
        if freq_rank is not None:
            try:
                midpoint = int(freq_rank)
            except (TypeError, ValueError):
                midpoint = None
        if midpoint is None:
            midpoint = _band_midpoint(str(bin_name) if bin_name is not None else None)

        if midpoint is None:
            midpoint = 3500

        weight = max(1.0, 10000.0 / float(midpoint))
        weighted_total_sum += weight
        weighted_correct_sum += weight * is_correct
        freq_points.append(int(midpoint))

        if bin_name is not None:
            key = str(bin_name)
            bin_seen.add(key)
            weighted_hits[key] = round(weighted_hits.get(key, 0.0) + (weight * is_correct), 3)

    raw_accuracy = correct / total
    weighted_accuracy = weighted_correct_sum / weighted_total_sum if weighted_total_sum > 0 else raw_accuracy

    score = (0.65 * raw_accuracy) + (0.35 * weighted_accuracy)

    if score >= 0.93:
        estimated_vocab_size = 9000
    elif score >= 0.85:
        estimated_vocab_size = 7500
    elif score >= 0.75:
        estimated_vocab_size = 5500
    elif score >= 0.63:
        estimated_vocab_size = 3800
    elif score >= 0.50:
        estimated_vocab_size = 2200
    elif score >= 0.35:
        estimated_vocab_size = 1400
    else:
        estimated_vocab_size = 700

    if estimated_vocab_size >= 8000:
        band = "8k+"
    elif estimated_vocab_size >= 6000:
        band = "6k-8k"
    elif estimated_vocab_size >= 4000:
        band = "4k-6k"
    elif estimated_vocab_size >= 2500:
        band = "2.5k-4k"
    elif estimated_vocab_size >= 1500:
        band = "1.5k-2.5k"
    else:
        band = "<1.5k"

    unique_bins = len(bin_seen)
    coverage_score = min(1.0, unique_bins / 4.0)

    if freq_points:
        avg_freq = sum(freq_points) / len(freq_points)
        difficulty_score = min(1.0, avg_freq / 6000.0)
        spread_score = min(1.0, (max(freq_points) - min(freq_points)) / 5000.0) if len(freq_points) >= 2 else 0.0
    else:
        difficulty_score = 0.0
        spread_score = 0.0

    sample_score = min(1.0, total / 24.0)

    confidence = (
        0.30 * sample_score
        + 0.20 * coverage_score
        + 0.15 * difficulty_score
        + 0.10 * spread_score
        + 0.25 * min(1.0, score)
    )
    confidence = round(max(0.15, min(confidence, 0.95)), 2)

    return {
        "estimated_vocab_size": estimated_vocab_size,
        "estimated_vocab_band": band,
        "confidence": confidence,
        "scoring_model": "runtime_scoring_v1",
        "coverage_score": round(coverage_score, 3),
        "difficulty_score": round(difficulty_score, 3),
        "spread_score": round(spread_score, 3),
        "sample_score": round(sample_score, 3),
        "weighted_bin_hits": weighted_hits,
    }


def _summary_text(
    *,
    correct: int,
    total: int,
    accuracy_pct: float,
    estimated_vocab_size: int | None,
    estimated_vocab_band: str | None,
    confidence: float | None,
) -> str:
    accuracy_text = str(int(accuracy_pct)) if float(accuracy_pct).is_integer() else str(accuracy_pct)
    parts = [f"Vocab finished. Score: {correct}/{total} ({accuracy_text}%)"]

    if estimated_vocab_size is not None:
        parts.append(f"Estimated vocabulary: ~{estimated_vocab_size} words")
    if estimated_vocab_band:
        parts.append(f"Band: {estimated_vocab_band}")
    if confidence is not None:
        conf_pct = round(float(confidence) * 100)
        parts.append(f"Confidence: {conf_pct}%")

    return "\n".join(parts)


def _attempt_total_from_row(row: sqlite3.Row) -> int:
    if "total_questions" in row.keys():
        return int(row["total_questions"] or 0)
    if "questions_answered" in row.keys():
        return int(row["questions_answered"] or 0)
    return 0


def _attempt_correct_from_row(row: sqlite3.Row) -> int:
    if "correct_answers" in row.keys():
        return int(row["correct_answers"] or 0)
    if "correct_count" in row.keys():
        return int(row["correct_count"] or 0)
    return 0


def _bump_item_exposure(conn: sqlite3.Connection, *, item_id: int) -> None:
    if not _table_exists(conn, table="vocab_item_exposure"):
        return
    if not _has_column(conn, table="vocab_item_exposure", column="item_id"):
        return
    if not _has_column(conn, table="vocab_item_exposure", column="shown_count"):
        return

    has_last_shown_at = _has_column(conn, table="vocab_item_exposure", column="last_shown_at")

    if has_last_shown_at:
        conn.execute(
            """
            INSERT INTO vocab_item_exposure (item_id, shown_count, last_shown_at)
            VALUES (?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(item_id) DO UPDATE SET
                shown_count = vocab_item_exposure.shown_count + 1,
                last_shown_at = CURRENT_TIMESTAMP
            """,
            (item_id,),
        )
        return

    conn.execute(
        """
        INSERT INTO vocab_item_exposure (item_id, shown_count)
        VALUES (?, 1)
        ON CONFLICT(item_id) DO UPDATE SET
            shown_count = vocab_item_exposure.shown_count + 1
        """,
        (item_id,),
    )


def start_attempt(conn: sqlite3.Connection, *, user_id: int) -> int:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id FROM vocab_attempts WHERE user_id = ? AND status = 'started' ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if row is not None:
        return int(row["id"])

    if _has_column(conn, table="vocab_attempts", column="total_questions"):
        cur = conn.execute(
            "INSERT INTO vocab_attempts (user_id, status, total_questions, correct_answers) VALUES (?, 'started', 0, 0)",
            (user_id,),
        )
    elif _has_column(conn, table="vocab_attempts", column="questions_answered"):
        cols = ["user_id", "status", "questions_answered", "correct_count"]
        vals: list[object] = [user_id, "started", 0, 0]
        if _has_column(conn, table="vocab_attempts", column="dont_know_count"):
            cols.append("dont_know_count")
            vals.append(0)
        if _has_column(conn, table="vocab_attempts", column="current_step"):
            cols.append("current_step")
            vals.append(0)
        if _has_column(conn, table="vocab_attempts", column="question_limit"):
            cols.append("question_limit")
            vals.append(24)
        placeholders = ", ".join("?" for _ in vals)
        cur = conn.execute(
            f"INSERT INTO vocab_attempts ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(vals),
        )
    else:
        cur = conn.execute(
            "INSERT INTO vocab_attempts (user_id, status) VALUES (?, 'started')",
            (user_id,),
        )

    conn.commit()
    return int(cur.lastrowid)


def get_active_attempt(conn: sqlite3.Connection, *, user_id: int) -> sqlite3.Row | None:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT * FROM vocab_attempts WHERE user_id = ? AND status = 'started' ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()


def log_event(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    user_id: int,
    item_id: int,
    event_type: str,
    answer_text: str | None = None,
    is_correct: int | None = None,
) -> int:
    conn.row_factory = sqlite3.Row

    event_columns: list[str] = []
    event_values: list[object] = []

    for column, value in [
        ("attempt_id", attempt_id),
        ("user_id", user_id),
        ("item_id", item_id),
        ("event_type", event_type),
        ("answer_text", answer_text),
        ("is_correct", is_correct),
    ]:
        if _has_column(conn, table="vocab_attempt_events", column=column):
            event_columns.append(column)
            event_values.append(value)

    placeholders = ", ".join("?" for _ in event_values)
    cur = conn.execute(
        f"INSERT INTO vocab_attempt_events ({', '.join(event_columns)}) VALUES ({placeholders})",
        tuple(event_values),
    )

    if event_type in ("answer", "dont_know"):
        if _has_column(conn, table="vocab_attempts", column="total_questions"):
            conn.execute(
                """
                UPDATE vocab_attempts
                SET total_questions = COALESCE(total_questions, 0) + 1,
                    correct_answers = COALESCE(correct_answers, 0) + CASE WHEN COALESCE(?, 0) = 1 THEN 1 ELSE 0 END
                WHERE id = ?
                """,
                (is_correct, attempt_id),
            )
        elif _has_column(conn, table="vocab_attempts", column="questions_answered"):
            updates = [
                "questions_answered = COALESCE(questions_answered, 0) + 1",
                "correct_count = COALESCE(correct_count, 0) + CASE WHEN COALESCE(?, 0) = 1 THEN 1 ELSE 0 END",
            ]
            params: list[object] = [is_correct]

            if event_type == "dont_know" and _has_column(conn, table="vocab_attempts", column="dont_know_count"):
                updates.append("dont_know_count = COALESCE(dont_know_count, 0) + 1")

            conn.execute(
                f"UPDATE vocab_attempts SET {', '.join(updates)} WHERE id = ?",
                (*params, attempt_id),
            )

    if event_type in ("shown", "question_shown"):
        _bump_item_exposure(conn, item_id=item_id)

    conn.commit()
    return int(cur.lastrowid)


def finish_attempt(
    conn: sqlite3.Connection,
    *,
    attempt_id: int,
    status: str = "finished",
    completion_reason: str | None = None,
) -> None:
    updates = ["status = ?", "finished_at = CURRENT_TIMESTAMP"]
    params: list[object] = [status]

    if completion_reason is not None and _has_column(conn, table="vocab_attempts", column="completion_reason"):
        updates.append("completion_reason = ?")
        params.append(completion_reason)

    conn.execute(
        f"UPDATE vocab_attempts SET {', '.join(updates)} WHERE id = ? AND status = 'started'",
        (*params, attempt_id),
    )
    conn.commit()


def get_attempt_stats(conn: sqlite3.Connection, *, attempt_id: int) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM vocab_attempts WHERE id = ?",
        (attempt_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError("attempt_not_found")

    total_questions = _attempt_total_from_row(row)
    correct_answers = _attempt_correct_from_row(row)
    wrong_answers = max(total_questions - correct_answers, 0)
    accuracy_pct = _format_accuracy_pct(correct_answers, total_questions)

    estimate = _estimate_vocab_metrics(conn, attempt_id=attempt_id, correct=correct_answers, total=total_questions)

    estimated_vocab_size = (
        row["estimated_vocab_size"]
        if "estimated_vocab_size" in row.keys() and row["estimated_vocab_size"] is not None
        else estimate["estimated_vocab_size"]
    )
    estimated_vocab_band = (
        row["estimated_vocab_band"]
        if "estimated_vocab_band" in row.keys() and row["estimated_vocab_band"] is not None
        else estimate["estimated_vocab_band"]
    )
    confidence = (
        row["confidence"]
        if "confidence" in row.keys() and row["confidence"] is not None
        else estimate["confidence"]
    )

    out: dict[str, Any] = {
        "attempt_id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "status": str(row["status"]),
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "wrong_answers": wrong_answers,
        "accuracy_pct": accuracy_pct,
        "estimated_vocab_size": estimated_vocab_size,
        "estimated_vocab_band": estimated_vocab_band,
        "confidence": confidence,
        "scoring_model": estimate["scoring_model"],
        "coverage_score": estimate["coverage_score"],
        "difficulty_score": estimate["difficulty_score"],
        "spread_score": estimate["spread_score"],
        "sample_score": estimate["sample_score"],
        "weighted_bin_hits": estimate["weighted_bin_hits"],
        "started_at": row["started_at"] if "started_at" in row.keys() else None,
        "finished_at": row["finished_at"] if "finished_at" in row.keys() else None,
    }

    if "completion_reason" in row.keys():
        out["completion_reason"] = row["completion_reason"]
    if "question_limit" in row.keys():
        out["question_limit"] = int(row["question_limit"] or 0)
    if "mode_run_id" in row.keys():
        out["mode_run_id"] = int(row["mode_run_id"]) if row["mode_run_id"] is not None else None

    out["summary_text"] = _summary_text(
        correct=correct_answers,
        total=total_questions,
        accuracy_pct=accuracy_pct,
        estimated_vocab_size=estimated_vocab_size,
        estimated_vocab_band=estimated_vocab_band,
        confidence=confidence if confidence is not None else None,
    )
    return out


def persist_finished_result(conn: sqlite3.Connection, *, attempt_id: int) -> dict[str, Any]:
    stats = get_attempt_stats(conn, attempt_id=attempt_id)

    update_parts: list[str] = []
    update_params: list[object] = []

    if _has_column(conn, table="vocab_attempts", column="estimated_vocab_size"):
        update_parts.append("estimated_vocab_size = ?")
        update_params.append(stats.get("estimated_vocab_size"))
    if _has_column(conn, table="vocab_attempts", column="estimated_vocab_band"):
        update_parts.append("estimated_vocab_band = ?")
        update_params.append(stats.get("estimated_vocab_band"))
    if _has_column(conn, table="vocab_attempts", column="confidence"):
        update_parts.append("confidence = ?")
        update_params.append(stats.get("confidence"))

    if update_parts:
        conn.execute(
            f"UPDATE vocab_attempts SET {', '.join(update_parts)} WHERE id = ?",
            (*update_params, attempt_id),
        )
        conn.commit()
        stats = get_attempt_stats(conn, attempt_id=attempt_id)

    if _table_exists(conn, table="vocab_result_snapshots"):
        existing = conn.execute(
            "SELECT id FROM vocab_result_snapshots WHERE attempt_id = ? AND step_index = ? LIMIT 1",
            (attempt_id, stats["total_questions"]),
        ).fetchone()

        payload_json = _json_dumps(stats)

        if existing is None:
            conn.execute(
                """
                INSERT INTO vocab_result_snapshots (
                    attempt_id,
                    step_index,
                    estimated_vocab_band,
                    estimated_vocab_size,
                    confidence,
                    snapshot_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    stats["total_questions"],
                    stats.get("estimated_vocab_band"),
                    stats.get("estimated_vocab_size"),
                    stats.get("confidence"),
                    payload_json,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE vocab_result_snapshots
                SET estimated_vocab_band = ?,
                    estimated_vocab_size = ?,
                    confidence = ?,
                    snapshot_payload_json = ?
                WHERE id = ?
                """,
                (
                    stats.get("estimated_vocab_band"),
                    stats.get("estimated_vocab_size"),
                    stats.get("confidence"),
                    payload_json,
                    int(existing[0]),
                ),
            )

    mode_run_id = stats.get("mode_run_id")
    if mode_run_id is not None and _table_exists(conn, table="mode_results"):
        existing = conn.execute(
            "SELECT id FROM mode_results WHERE run_id = ? AND mode = 'vocab' LIMIT 1",
            (mode_run_id,),
        ).fetchone()

        payload_json = _json_dumps(stats)
        params = (
            "vocab",
            mode_run_id,
            stats["user_id"],
            "runtime_scoring_v1",
            stats["accuracy_pct"],
            str(stats.get("estimated_vocab_band") or f"{stats['correct_answers']}/{stats['total_questions']}"),
            None,
            stats.get("confidence"),
            payload_json,
        )

        if existing is None:
            conn.execute(
                """
                INSERT INTO mode_results (
                    mode,
                    run_id,
                    user_id,
                    result_version,
                    score_numeric,
                    band_text,
                    cefr_level,
                    confidence,
                    result_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
        else:
            conn.execute(
                """
                UPDATE mode_results
                SET result_version = ?,
                    score_numeric = ?,
                    band_text = ?,
                    cefr_level = ?,
                    confidence = ?,
                    result_payload_json = ?
                WHERE id = ?
                """,
                (
                    "runtime_scoring_v1",
                    stats["accuracy_pct"],
                    str(stats.get("estimated_vocab_band") or f"{stats['correct_answers']}/{stats['total_questions']}"),
                    None,
                    stats.get("confidence"),
                    payload_json,
                    int(existing[0]),
                ),
            )

    conn.commit()
    return stats
