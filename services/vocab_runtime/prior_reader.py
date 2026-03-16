from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from services.vocab_runtime.result_snapshot import compute_is_usable_as_level_prior

logger = logging.getLogger(__name__)


def get_latest_vocab_prior_from_sqlite(db_path: str, user_id: int) -> dict[str, Any] | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT id, finished_at, result_snapshot_json
            FROM vocab_attempts
            WHERE user_id = ?
              AND finished_at IS NOT NULL
              AND result_snapshot_json IS NOT NULL
            ORDER BY finished_at DESC, id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            return None

        try:
            snapshot = json.loads(row["result_snapshot_json"])
            if not isinstance(snapshot, dict):
                logger.warning("Malformed vocab snapshot for attempt_id=%s: not a dict", row["id"])
                return None
        except Exception:
            logger.exception("Failed to decode vocab snapshot for attempt_id=%s", row["id"])
            return None

        fresh_until_days = snapshot.get("fresh_until_days", 90)
        return {
            "attempt_id": row["id"],
            "finished_at": row["finished_at"],
            "snapshot": snapshot,
            "is_usable_as_level_prior": compute_is_usable_as_level_prior(
                finished_at_iso=row["finished_at"],
                fresh_until_days=int(fresh_until_days),
            ),
        }
    finally:
        conn.close()


def get_latest_vocab_prior(conn_or_db_path, *, user_id: int):
    if hasattr(conn_or_db_path, "execute"):
        import json
        import logging

        logger = logging.getLogger(__name__)
        conn = conn_or_db_path
        row = conn.execute(
            """
            SELECT id, finished_at, result_snapshot_json
            FROM vocab_attempts
            WHERE user_id = ?
              AND finished_at IS NOT NULL
              AND result_snapshot_json IS NOT NULL
            ORDER BY finished_at DESC, id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            return None

        try:
            snapshot = json.loads(row["result_snapshot_json"])
            if not isinstance(snapshot, dict):
                logger.warning("Malformed vocab snapshot for attempt_id=%s: not a dict", row["id"])
                return None
        except Exception:
            logger.exception("Failed to decode vocab snapshot for attempt_id=%s", row["id"])
            return None

        fresh_until_days = snapshot.get("fresh_until_days", 90)
        return {
            "attempt_id": row["id"],
            "finished_at": row["finished_at"],
            "snapshot": snapshot,
            "is_usable_as_level_prior": compute_is_usable_as_level_prior(
                finished_at_iso=row["finished_at"],
                fresh_until_days=int(fresh_until_days),
            ),
        }

    return get_latest_vocab_prior_from_sqlite(str(conn_or_db_path), user_id)
