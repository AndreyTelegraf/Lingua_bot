from __future__ import annotations

import logging
import os
import sqlite3

from aiogram import F, Router
from aiogram.types import Message

ADMIN_TELEGRAM_ID = 336224597

router = Router(name="admin_stats")
log = logging.getLogger(__name__)


def build_admin_stats_router() -> Router:
    return router


def _db_path() -> str:
    return os.getenv("DB_PATH", "/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    try:
        rows = conn.execute("PRAGMA table_info(%s)" % table_name).fetchall()
        return {r[1] for r in rows}
    except Exception:
        return set()


def _safe_scalar(conn: sqlite3.Connection, sql: str) -> int:
    try:
        row = conn.execute(sql).fetchone()
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def _count_error_report_clicks(conn: sqlite3.Connection) -> int:
    total = 0

    candidates = [
        ("vocab_attempt_events", [
            "report_error",
            "report_clicked",
            "report_button_clicked",
            "report",
            "error_report",
        ]),
        ("attempt_events", [
            "report_error",
            "report_clicked",
            "report_button_clicked",
            "report",
            "error_report",
        ]),
    ]

    for table_name, event_names in candidates:
        if not _table_exists(conn, table_name):
            continue

        cols = _table_columns(conn, table_name)

        # Exact event_type match
        if "event_type" in cols:
            in_list = ", ".join("{}".format(x) for x in event_names)
            total += _safe_scalar(
                conn,
                "SELECT COUNT(*) FROM %s WHERE event_type IN (%s)" % (table_name, in_list),
            )

        # button_code / code match
        if "button_code" in cols:
            total += _safe_scalar(
                conn,
                "SELECT COUNT(*) FROM %s WHERE LOWER(button_code) LIKE '%%report%%' OR LOWER(button_code) LIKE '%%error%%'" % table_name,
            )

        if "code" in cols:
            total += _safe_scalar(
                conn,
                "SELECT COUNT(*) FROM %s WHERE LOWER(code) LIKE '%%report%%' OR LOWER(code) LIKE '%%error%%'" % table_name,
            )

        # payload text heuristics
        for payload_col in ("payload", "payload_json", "meta_json", "details"):
            if payload_col in cols:
                total += _safe_scalar(
                    conn,
                    "SELECT COUNT(*) FROM %s WHERE LOWER(%s) LIKE '%%report%%' OR LOWER(%s) LIKE '%%error%%'" % (
                        table_name, payload_col, payload_col
                    ),
                )

    return total


@router.message(F.text)
async def admin_stats(message: Message) -> None:
    text = (message.text or "").strip()
    user_id = message.from_user.id if message.from_user else None

    if not text.startswith("/stats"):
        return

    log.warning("admin_stats_hit text=%r from_user_id=%r", text, user_id)

    if user_id != ADMIN_TELEGRAM_ID:
        return

    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row

    users_total = _safe_scalar(conn, "SELECT COUNT(*) FROM users")
    attempts_total = _safe_scalar(conn, "SELECT COUNT(*) FROM vocab_attempts")
    completed_attempts = _safe_scalar(conn, "SELECT COUNT(*) FROM vocab_attempts WHERE status = 'completed'")
    answers_total = _safe_scalar(conn, "SELECT COUNT(*) FROM vocab_answers")
    error_report_clicks = _count_error_report_clicks(conn)

    completion_rate = 0.0
    if attempts_total > 0:
        completion_rate = round((completed_attempts / attempts_total) * 100.0, 1)

    rows = conn.execute("""
        SELECT
          user_id,
          COUNT(*) AS attempts_n,
          SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_n,
          MAX(COALESCE(correct_count, 0)) AS best_correct,
          MAX(COALESCE(finished_at, started_at, created_at, updated_at)) AS last_seen
        FROM vocab_attempts
        GROUP BY user_id
        ORDER BY attempts_n DESC
        LIMIT 10
    """).fetchall()

    conn.close()

    lines = []
    lines.append("<b>LinguaBot stats</b>")
    lines.append("Users: <b>%s</b>" % users_total)
    lines.append("Attempts: <b>%s</b>" % attempts_total)
    lines.append("Completed attempts: <b>%s</b>" % completed_attempts)
    lines.append("Completion rate: <b>%s%%</b>" % completion_rate)
    lines.append("Answers: <b>%s</b>" % answers_total)
    lines.append("Error reports clicked: <b>%s</b>" % error_report_clicks)
    lines.append("")
    lines.append("<b>Top users:</b>")

    if rows:
        for r in rows:
            uid = r["user_id"]
            attempts_n = r["attempts_n"]
            completed_n = r["completed_n"]
            best_correct = r["best_correct"] or 0
            last_seen = r["last_seen"] or "-"

            line = (
                "<code>%s</code> — attempts: %s, completed: %s, best_correct: %s, last_seen: %s"
                % (uid, attempts_n, completed_n, best_correct, last_seen)
            )
            lines.append(line)
    else:
        lines.append("— no attempts yet")

    await message.answer("\n".join(lines), parse_mode="HTML")
