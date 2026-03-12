from __future__ import annotations

import sqlite3


def get_next_item(conn: sqlite3.Connection, *, attempt_id: int) -> sqlite3.Row | None:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT vi.id, vi.lemma, vi.question_text, vi.correct_answer, vi.pos
        FROM vocab_items vi
        WHERE vi.is_active = 1
          AND vi.id NOT IN (
            SELECT item_id
            FROM vocab_attempt_events
            WHERE attempt_id = ?
              AND event_type = 'shown'
        )
        ORDER BY vi.id ASC
        LIMIT 1
        """,
        (attempt_id,),
    ).fetchone()
