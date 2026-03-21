from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import Any

from .session import CATSessionState, restore_cat_session, serialize_cat_session


def ensure_cat_runtime_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cat_sessions (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            modality TEXT NOT NULL,
            status TEXT NOT NULL,
            session_payload_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cat_session_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def save_cat_session(conn: sqlite3.Connection, session: CATSessionState) -> None:
    ensure_cat_runtime_tables(conn)
    payload = serialize_cat_session(session)
    conn.execute(
        """
        INSERT INTO cat_sessions (
            session_id, user_id, modality, status, session_payload_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id) DO UPDATE SET
            user_id = excluded.user_id,
            modality = excluded.modality,
            status = excluded.status,
            session_payload_json = excluded.session_payload_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            session.session_id,
            int(session.user_id),
            str(session.modality),
            str(session.status),
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ),
    )
    conn.commit()


def load_cat_session(conn: sqlite3.Connection, *, session_id: str) -> CATSessionState | None:
    ensure_cat_runtime_tables(conn)
    row = conn.execute(
        """
        SELECT session_payload_json
        FROM cat_sessions
        WHERE session_id = ?
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    payload = json.loads(row[0])
    return restore_cat_session(payload)


def append_cat_session_event(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> int:
    ensure_cat_runtime_tables(conn)
    cur = conn.execute(
        """
        INSERT INTO cat_session_events (session_id, event_type, payload_json)
        VALUES (?, ?, ?)
        """,
        (
            session_id,
            event_type,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_cat_session_events(conn: sqlite3.Connection, *, session_id: str) -> list[dict[str, Any]]:
    ensure_cat_runtime_tables(conn)
    rows = conn.execute(
        """
        SELECT id, session_id, event_type, payload_json, created_at
        FROM cat_session_events
        WHERE session_id = ?
        ORDER BY id ASC
        """,
        (session_id,),
    ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "id": int(row[0]),
                "session_id": str(row[1]),
                "event_type": str(row[2]),
                "payload": json.loads(row[3]),
                "created_at": row[4],
            }
        )
    return out
