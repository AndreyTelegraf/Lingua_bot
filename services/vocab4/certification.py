from __future__ import annotations

import json
import sqlite3


def load_pending_authoring_items(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, source_name, lemma, pos, bin_name, prompt, correct_choice,
               distractors_json, cert_status, reject_reason, reviewer_notes,
               payload_json, promoted_item_id, created_at, updated_at
        FROM vocab4_authoring_items
        WHERE cert_status = 'pending'
        ORDER BY id ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def reject_authoring_item(
    conn: sqlite3.Connection,
    authoring_id: int,
    reason: str,
    reviewer_notes: str = "",
) -> None:
    cursor = conn.execute(
        """
        UPDATE vocab4_authoring_items
        SET cert_status = 'rejected',
            reject_reason = ?,
            reviewer_notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND cert_status = 'pending'
        """,
        (reason, reviewer_notes, authoring_id),
    )
    if cursor.rowcount == 0:
        raise ValueError(f"authoring_id={authoring_id} not found or not pending")
    conn.commit()


def promote_authoring_item(
    conn: sqlite3.Connection,
    authoring_id: int,
    reviewer_notes: str = "",
) -> int:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, payload_json FROM vocab4_authoring_items WHERE id = ?",
        (authoring_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"authoring_id={authoring_id} not found")

    payload = json.loads(row["payload_json"])
    choices = payload["choices"]  # [correct_choice, d1, d2, d3, d4, d5]

    try:
        cursor = conn.execute(
            """
            INSERT INTO vocab4_items
                (lemma, pos, bin_name, prompt, correct_choice, is_active, cert_status, diagnostic_tags)
            VALUES (?, ?, ?, ?, ?, 1, 'certified', '{}')
            """,
            (
                payload["lemma"],
                payload["pos"],
                payload["bin_name"],
                payload["prompt"],
                payload["correct_choice"],
            ),
        )
        runtime_item_id = cursor.lastrowid

        for position_index, choice_text in enumerate(choices):
            conn.execute(
                """
                INSERT INTO vocab4_choices (item_id, choice_text, is_correct, position_index)
                VALUES (?, ?, ?, ?)
                """,
                (runtime_item_id, choice_text, 1 if position_index == 0 else 0, position_index),
            )

        update_cursor = conn.execute(
            """
            UPDATE vocab4_authoring_items
            SET cert_status = 'certified',
                promoted_item_id = ?,
                reviewer_notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND cert_status = 'pending'
            """,
            (runtime_item_id, reviewer_notes, authoring_id),
        )
        if update_cursor.rowcount == 0:
            raise ValueError(f"authoring_id={authoring_id} is not pending")

        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return runtime_item_id
