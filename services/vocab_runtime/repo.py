from __future__ import annotations
import uuid

from services.vocab_runtime.result_snapshot import build_vocab_result_snapshot

import json
import sqlite3
from typing import Any

from services.vocab_runtime.scoring import (
    build_scoring_input_from_events,
    extract_scoring_rows_from_event_rows,
    score_attempt_default,
)



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


def _compact_band_text(band: str | None, size: int | None) -> str | None:
    band = str(band or "").strip()
    size = int(size or 0)
    mapping = {
        "<1.5k": "до 1 500",
        "1.5k-2.5k": "1 500–2 500",
        "2.5k-4k": "2 500–4 000",
        "4k-6k": "4 000–6 000",
        "6k-8k": "6 000–8 000",
        "8k+": "от 8 000",
    }
    if band in mapping:
        return mapping[band]
    if size <= 0:
        return None
    if size < 1500:
        return "до 1 500"
    if size < 2500:
        return "1 500–2 500"
    if size < 4000:
        return "2 500–4 000"
    if size < 6000:
        return "4 000–6 000"
    if size < 8000:
        return "6 000–8 000"
    return "от 8 000"


def _current_vocab_baseline_payload(stats: dict[str, Any]) -> dict[str, Any]:
    vocab_size = stats.get("estimated_vocab_size")
    vocab_band = stats.get("estimated_vocab_band")
    confidence = stats.get("confidence")

    cefr_guess = None
    size = int(vocab_size or 0)
    if size > 0:
        if size < 1000:
            cefr_guess = "A1"
        elif size < 2500:
            cefr_guess = "A2"
        elif size < 4000:
            cefr_guess = "B1"
        elif size < 7000:
            cefr_guess = "B2"
        else:
            cefr_guess = "C1"

    readiness = "below_a2"
    if cefr_guess in {"A2", "B1", "B2", "C1"}:
        readiness = "around_a2_or_above"

    return {
        "mode": "vocab",
        "estimated_vocab_size": vocab_size,
        "estimated_vocab_band": vocab_band,
        "estimated_cefr_level": cefr_guess,
        "confidence": confidence,
        "question_count": stats.get("total_questions"),
        "correct_answers": stats.get("correct_answers"),
        "scoring_model": stats.get("scoring_model"),
        "calibration_hint": {
            "level_entry_cefr_floor": cefr_guess,
            "level_entry_cefr_guess": cefr_guess,
            "ciple_entry_readiness": readiness,
        },
    }


def get_active_user_baseline(conn: sqlite3.Connection, *, user_id: int, mode: str) -> dict[str, Any] | None:
    if not _table_exists(conn, table="user_mode_baselines"):
        return None

    conn.row_factory = sqlite3.Row
    row = conn.execute(
        '''
        SELECT *
        FROM user_mode_baselines
        WHERE user_id = ?
          AND mode = ?
          AND is_active = 1
        ORDER BY id DESC
        LIMIT 1
        ''',
        (user_id, mode),
    ).fetchone()
    if row is None:
        return None
    out = dict(row)
    payload = out.get("calibration_payload_json")
    if payload:
        try:
            out["calibration_payload_json"] = json.loads(str(payload))
        except Exception:
            pass
    return out


def _derive_progress_event_type(previous_payload: dict[str, Any] | None, current_payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if previous_payload is None:
        return "baseline_created", {
            "previous_vocab_size": None,
            "current_vocab_size": current_payload.get("estimated_vocab_size"),
        }

    prev_band = str(previous_payload.get("estimated_vocab_band") or "")
    curr_band = str(current_payload.get("estimated_vocab_band") or "")
    prev_size = int(previous_payload.get("estimated_vocab_size") or 0)
    curr_size = int(current_payload.get("estimated_vocab_size") or 0)

    delta_size = curr_size - prev_size
    meaningful = abs(delta_size) >= 400

    if prev_band != curr_band:
        order = {
            "<1.5k": 1,
            "1.5k-2.5k": 2,
            "2.5k-4k": 3,
            "4k-6k": 4,
            "6k-8k": 5,
            "8k+": 6,
        }
        if order.get(curr_band, 0) > order.get(prev_band, 0):
            event = "result_improved"
        elif order.get(curr_band, 0) < order.get(prev_band, 0):
            event = "result_declined"
        else:
            event = "result_stable"
    else:
        if delta_size >= 400 and meaningful:
            event = "result_improved"
        elif delta_size <= -400 and meaningful:
            event = "result_declined"
        else:
            event = "result_stable"

    return event, {
        "previous_vocab_size": prev_size,
        "current_vocab_size": curr_size,
        "delta_vocab_size": delta_size,
        "previous_vocab_band": prev_band,
        "current_vocab_band": curr_band,
    }


def _attach_previous_result_summary(stats: dict[str, Any], previous_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not previous_payload:
        return stats

    prev_total = previous_payload.get("question_count")
    prev_correct = previous_payload.get("correct_answers")
    prev_band = previous_payload.get("estimated_vocab_band")
    prev_size = previous_payload.get("estimated_vocab_size")

    stats["previous_correct_answers"] = prev_correct
    stats["previous_total_questions"] = prev_total
    stats["previous_estimated_vocab_band"] = prev_band
    stats["previous_estimated_vocab_size"] = prev_size
    stats["previous_vocab_range_compact"] = _compact_band_text(prev_band, prev_size)

    return stats


def _upsert_user_mode_baseline(conn: sqlite3.Connection, *, stats: dict[str, Any], mode: str = "vocab") -> dict[str, Any]:
    if not _table_exists(conn, table="user_mode_baselines"):
        return stats

    user_id = int(stats["user_id"])
    previous = get_active_user_baseline(conn, user_id=user_id, mode=mode)

    previous_payload = None
    if previous is not None:
        payload = previous.get("calibration_payload_json")
        if isinstance(payload, dict):
            previous_payload = payload
        else:
            previous_payload = {
                "estimated_vocab_size": previous.get("estimated_vocab_size"),
                "estimated_vocab_band": previous.get("estimated_vocab_band"),
                "estimated_cefr_level": previous.get("estimated_cefr_level"),
                "confidence": previous.get("confidence"),
            }

    stats = _attach_previous_result_summary(stats, previous_payload)
    current_payload = _current_vocab_baseline_payload(stats)
    event_type, delta_payload = _derive_progress_event_type(previous_payload, current_payload)

    if previous is not None:
        conn.execute(
            '''
            UPDATE user_mode_baselines
            SET is_active = 0,
                valid_until = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''',
            (int(previous["id"]),),
        )

    conn.execute(
        '''
        INSERT INTO user_mode_baselines (
            user_id,
            mode,
            baseline_version,
            source_mode,
            source_run_id,
            source_attempt_id,
            estimated_vocab_size,
            estimated_vocab_band,
            estimated_cefr_level,
            confidence,
            calibration_payload_json,
            valid_from,
            is_active,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''',
        (
            user_id,
            mode,
            "vocab_baseline_v1",
            "vocab",
            stats.get("mode_run_id"),
            stats.get("attempt_id"),
            current_payload.get("estimated_vocab_size"),
            current_payload.get("estimated_vocab_band"),
            current_payload.get("estimated_cefr_level"),
            current_payload.get("confidence"),
            _json_dumps(current_payload),
        ),
    )

    if _table_exists(conn, table="user_progress_events"):
        conn.execute(
            '''
            INSERT INTO user_progress_events (
                user_id,
                mode,
                source_run_id,
                source_attempt_id,
                event_type,
                previous_payload_json,
                current_payload_json,
                delta_payload_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''',
            (
                user_id,
                mode,
                stats.get("mode_run_id"),
                stats.get("attempt_id"),
                event_type,
                _json_dumps(previous_payload) if previous_payload is not None else None,
                _json_dumps(current_payload),
                _json_dumps(delta_payload),
            ),
        )

    conn.commit()
    return stats


def _format_accuracy_pct(correct: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((correct / total) * 100.0, 1)




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

def _load_scoring_rows(conn: sqlite3.Connection, *, attempt_id: int) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row

    has_answers = _table_exists(conn, table="vocab_answers")
    has_items = _table_exists(conn, table="vocab_items")

    if has_answers and has_items:
        rows = conn.execute(
            """
            SELECT
                va.is_correct AS is_correct,
                vi.bin_name AS bin_name,
                vi.freq_rank AS freq_rank
            FROM vocab_answers va
            LEFT JOIN vocab_items vi ON vi.id = va.item_id
            WHERE va.attempt_id = ?
            ORDER BY va.id ASC
            """,
            (attempt_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    rows = conn.execute(
        """
        SELECT event_type, payload_json
        FROM vocab_attempt_events
        WHERE attempt_id = ?
        ORDER BY id ASC
        """,
        (attempt_id,),
    ).fetchall()

    plain_rows = [dict(row) for row in rows]
    return extract_scoring_rows_from_event_rows(plain_rows)



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
        parts.append(f"Confidence: {round(float(confidence) * 100)}%")

    return "\n".join(parts)


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


def start_attempt(conn: sqlite3.Connection, *, user_id: int, mode_run_id: str | None = None) -> int:
    conn.row_factory = sqlite3.Row

    if mode_run_id is None:
        mode_run_id = str(uuid.uuid4())

    if _has_column(conn, table="vocab_attempts", column="questions_answered"):
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
        if _has_column(conn, table="vocab_attempts", column="mode_run_id"):
            cols.append("mode_run_id")
            vals.append(str(mode_run_id))
        placeholders = ", ".join("?" for _ in vals)
        cur = conn.execute(
            f"INSERT INTO vocab_attempts ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(vals),
        )
    elif _has_column(conn, table="vocab_attempts", column="total_questions"):
        cols = ["user_id", "status", "total_questions", "correct_answers"]
        vals: list[object] = [user_id, "started", 0, 0]
        if _has_column(conn, table="vocab_attempts", column="mode_run_id"):
            cols.append("mode_run_id")
            vals.append(str(mode_run_id))
        placeholders = ", ".join("?" for _ in vals)
        cur = conn.execute(
            f"INSERT INTO vocab_attempts ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(vals),
        )
    else:
        cols = ["user_id", "status"]
        vals: list[object] = [user_id, "started"]
        if _has_column(conn, table="vocab_attempts", column="mode_run_id"):
            cols.append("mode_run_id")
            vals.append(str(mode_run_id))
        placeholders = ", ".join("?" for _ in vals)
        cur = conn.execute(
            f"INSERT INTO vocab_attempts ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(vals),
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

    has_bin_name = _has_column(conn, table="vocab_items", column="bin_name")
    has_freq_rank = _has_column(conn, table="vocab_items", column="freq_rank")

    select_bits = ["vae.is_correct AS is_correct"]
    select_bits.append("vi.bin_name AS bin_name" if has_bin_name else "NULL AS bin_name")
    select_bits.append("vi.freq_rank AS freq_rank" if has_freq_rank else "NULL AS freq_rank")

    try:
        event_rows = conn.execute(
            f"""
            SELECT {', '.join(select_bits)}
            FROM vocab_attempt_events vae
            LEFT JOIN vocab_items vi ON vi.id = vae.item_id
            WHERE vae.attempt_id = ?
              AND vae.event_type = 'answer'
            ORDER BY vae.id ASC
            """,
            (attempt_id,),
        ).fetchall()

        scoring_input = build_scoring_input_from_events(
            [dict(r) for r in event_rows],
            attempt_id=attempt_id,
            total_questions=total_questions,
            correct_answers=correct_answers,
        )
        estimate = score_attempt_default(scoring_input)
    except sqlite3.OperationalError:
        estimate = {
            "estimated_vocab_size": row["estimated_vocab_size"] if "estimated_vocab_size" in row.keys() else None,
            "estimated_vocab_band": row["estimated_vocab_band"] if "estimated_vocab_band" in row.keys() else None,
            "confidence": row["confidence"] if "confidence" in row.keys() else None,
            "scoring_model": "runtime_scoring_fallback_from_attempt_row",
            "coverage_score": None,
            "difficulty_score": None,
            "spread_score": None,
            "sample_score": None,
            "weighted_bin_hits": {},
        }

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
        out["mode_run_id"] = str(row["mode_run_id"]) if row["mode_run_id"] is not None else None

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

    try:
        product_band, confidence, snapshot_json = _build_vocab_attempt_snapshot_payload_from_stats(stats=stats)
        try:
            conn.execute(
                """
                UPDATE vocab_attempts
                SET product_band = ?,
                    result_snapshot_json = ?
                WHERE id = ?
                """,
                (product_band, snapshot_json, attempt_id),
            )
            stats["product_band"] = product_band
            stats["result_snapshot_json"] = snapshot_json
            if confidence is not None:
                stats["confidence"] = confidence
        except sqlite3.OperationalError:
            pass
    except Exception:
        pass

    conn.commit()
    stats = _upsert_user_mode_baseline(conn, stats=stats, mode="vocab")
    return stats


def _build_vocab_attempt_snapshot_payload(*, range_min: int, range_max: int, correct_answers: int, total_questions: int, finished_at: str) -> tuple[str, str, str]:
    snapshot = build_vocab_result_snapshot(
        range_min=range_min,
        range_max=range_max,
        correct_count=correct_answers,
        total_questions=total_questions,
        generated_at=finished_at,
    )
    return snapshot.product_band, snapshot.confidence, snapshot.to_json_text()


def _band_to_range_from_estimated_vocab_size(estimated_vocab_size: int | None) -> tuple[int, int]:
    size = int(estimated_vocab_size or 0)
    if size < 500:
        return (0, 500)
    if size <= 1000:
        return (500, 1000)
    if size <= 1500:
        return (1000, 1500)
    if size <= 2500:
        return (1500, 2500)
    if size <= 4000:
        return (2500, 4000)
    if size <= 6500:
        return (4000, 6500)
    if size <= 8000:
        return (6500, 8000)
    return (8000, 12000)


def _build_vocab_attempt_snapshot_payload_from_stats(*, stats: dict[str, Any]) -> tuple[str, float | None, str]:
    estimated_vocab_size = stats.get("estimated_vocab_size")
    range_min, range_max = _band_to_range_from_estimated_vocab_size(estimated_vocab_size)

    total_questions = int(
        stats.get("total_questions")
        or stats.get("question_limit")
        or stats.get("questions_answered")
        or 24
    )
    correct_answers = int(
        stats.get("correct_answers")
        or 0
    )

    dont_know_count = stats.get("dont_know_count")
    dont_know_rate = None
    if dont_know_count is not None and total_questions > 0:
        dont_know_rate = float(dont_know_count) / float(total_questions)

    snapshot = build_vocab_result_snapshot(
        range_min=range_min,
        range_max=range_max,
        correct_count=correct_answers,
        total_questions=total_questions,
        confidence="medium",
        dont_know_rate=dont_know_rate,
        fast_answer_rate=None,
        slow_answer_rate=None,
        generated_at=str(stats.get("finished_at") or ""),
    )
    return snapshot.product_band, stats.get("confidence"), snapshot.to_json_text()
