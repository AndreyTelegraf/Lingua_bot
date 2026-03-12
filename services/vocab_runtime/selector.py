from __future__ import annotations

import sqlite3


def _has_column(conn: sqlite3.Connection, *, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    for row in rows:
        name = row[1] if not isinstance(row, sqlite3.Row) else row["name"]
        if str(name) == column:
            return True
    return False


def get_next_item(conn: sqlite3.Connection, *, attempt_id: int) -> sqlite3.Row | None:
    conn.row_factory = sqlite3.Row

    order_sql = "ORDER BY vi.id ASC"
    if _has_column(conn, table="vocab_items", column="freq_rank"):
        order_sql = '''
        ORDER BY
          CASE WHEN vi.freq_rank IS NULL THEN 1 ELSE 0 END ASC,
          vi.freq_rank ASC,
          vi.id ASC
        '''.strip()

    sql = f'''
        SELECT vi.id, vi.lemma, vi.question_text, vi.correct_answer, vi.pos
        FROM vocab_items vi
        WHERE vi.is_active = 1
          AND vi.id NOT IN (
            SELECT item_id
            FROM vocab_attempt_events
            WHERE attempt_id = ?
              AND event_type = 'shown'
          )
        {order_sql}
        LIMIT 1
    '''

    return conn.execute(sql, (attempt_id,)).fetchone()
