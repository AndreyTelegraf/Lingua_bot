from __future__ import annotations

import sqlite3


def build_question_payload(conn: sqlite3.Connection, *, item_id: int, attempt_id: int) -> dict[str, object]:
    conn.row_factory = sqlite3.Row

    item = conn.execute(
        'SELECT id, lemma, question_text, pos FROM vocab_items_runtime_v3 WHERE id = ?',
        (item_id,),
    ).fetchone()
    if item is None:
        raise RuntimeError("item_not_found")

    choices = conn.execute(
        'SELECT id, choice_text, position_index FROM vocab_choices_v3 WHERE item_id = ? ORDER BY position_index',
        (item_id,),
    ).fetchall()
    if len(choices) != 6:
        raise RuntimeError("invalid_choice_count")

    return {
        "attempt_id": attempt_id,
        "item_id": int(item["id"]),
        "lemma": str(item["lemma"]),
        "question_text": str(item["question_text"]),
        "pos": str(item["pos"] or ""),
        "choices": [
            {
                "choice_id": int(row["id"]),
                "choice_text": str(row["choice_text"]),
                "position_index": int(row["position_index"]),
            }
            for row in choices
        ],
    }
