from __future__ import annotations

import aiosqlite


class VocabRenderer:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def build_question_payload(self, *, item_id: int) -> dict[str, object]:
        cursor = await self.conn.execute(
            """
            SELECT id, lemma, question_text, correct_answer
            FROM vocab_items
            WHERE id = ?
            """,
            (item_id,),
        )
        item = await cursor.fetchone()
        if item is None:
            raise RuntimeError("vocab_item_not_found")

        cursor = await self.conn.execute(
            """
            SELECT id, choice_text, is_correct, position_index
            FROM vocab_choices
            WHERE item_id = ?
            ORDER BY position_index
            """,
            (item_id,),
        )
        choices = await cursor.fetchall()

        if len(choices) != 6:
            raise RuntimeError("invalid_vocab_choice_count")

        return {
            "item_id": int(item["id"]),
            "lemma": str(item["lemma"]),
            "question_text": str(item["lemma"]),
            "correct_answer": str(item["correct_answer"]),
            "choices": [
                {
                    "choice_id": int(row["id"]),
                    "choice_text": str(row["choice_text"]),
                    "position_index": int(row["position_index"]) + 1,
                }
                for row in choices
            ],
        }
