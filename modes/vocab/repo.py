from __future__ import annotations

import json
from dataclasses import asdict

import aiosqlite
from aiogram.types import User as TgUser

from domain.shared.enums import ModeCode
from modes.vocab.state import SelectorRuntimeState


class VocabRepository:
    async def _table_exists(self, table: str) -> bool:
        cur = await self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            (table,),
        )
        row = await cur.fetchone()
        return row is not None

    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def upsert_user_from_telegram(self, tg_user: TgUser) -> int:
        await self.conn.execute(
            """
            INSERT INTO users (
                telegram_user_id, username, first_name, last_name, language_code, is_bot
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                language_code = excluded.language_code,
                is_bot = excluded.is_bot,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                tg_user.id,
                tg_user.username,
                tg_user.first_name,
                tg_user.last_name,
                tg_user.language_code,
                int(tg_user.is_bot),
            ),
        )
        await self.conn.commit()

        cursor = await self.conn.execute(
            "SELECT id FROM users WHERE telegram_user_id = ?",
            (tg_user.id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("user_upsert_failed")
        return int(row["id"])

    async def create_mode_run(self, *, user_id: int, prior_payload: dict[str, object] | None) -> int:
        payload = json.dumps(prior_payload or {}, ensure_ascii=False)
        cursor = await self.conn.execute(
            """
            INSERT INTO mode_runs (
                mode, user_id, status, prior_payload_json
            )
            VALUES (?, ?, ?, ?)
            """,
            (ModeCode.VOCAB.value, user_id, "started", payload),
        )
        await self.conn.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("mode_run_not_created")
        return int(cursor.lastrowid)

    async def create_vocab_attempt(self, *, mode_run_id: int, user_id: int) -> int:
        cursor = await self.conn.execute(
            """
            INSERT INTO vocab_attempts (
                mode_run_id, user_id, status, current_step, question_limit,
                questions_answered, correct_count, dont_know_count, total_reject_count, hard_reject_streak
            )
            VALUES (?, ?, ?, 0, 24, 0, 0, 0, 0, 0)
            """,
            (mode_run_id, user_id, "started"),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("vocab_attempt_not_created")

        attempt_id = int(cursor.lastrowid)

        await self.conn.execute(
            """
            INSERT INTO vocab_selector_state(
                attempt_id,
                selector_payload_json,
                shown_item_ids_json,
                pos_counters_json,
                cefr_counters_json,
                bin_counters_json,
                current_item_meta_json
            )
            VALUES (?, '{}', '[]', '{}', '{}', '{}', '{}')
            """,
            (attempt_id,),
        )
        await self.conn.commit()
        return attempt_id

    async def get_active_vocab_attempt(self, *, user_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            """
            SELECT va.*, mr.id AS mode_run_id
            FROM vocab_attempts va
            JOIN mode_runs mr ON mr.id = va.mode_run_id
            WHERE va.user_id = ?
              AND va.status = 'started'
              AND mr.mode = ?
              AND mr.status = 'started'
            ORDER BY va.id DESC
            LIMIT 1
            """,
            (user_id, ModeCode.VOCAB.value),
        )
        return await cursor.fetchone()

    async def append_attempt_event(
        self,
        *,
        attempt_id: int,
        user_id: int,
        event_type: str,
        step_index: int | None = None,
        item_id: int | None = None,
        reason_code: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        payload_json = json.dumps(payload or {}, ensure_ascii=False)
        await self.conn.execute(
            """
            INSERT INTO vocab_attempt_events (
                attempt_id, user_id, event_type, step_index, item_id, reason_code, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (attempt_id, user_id, event_type, step_index, item_id, reason_code, payload_json),
        )
        await self.conn.commit()


    async def ensure_item_exposure_row(self, *, item_id: int) -> None:
        await self.conn.execute(
            """
            INSERT INTO vocab_item_exposure(item_id)
            VALUES (?)
            ON CONFLICT(item_id) DO NOTHING
            """,
            (item_id,),
        )
        await self.conn.commit()

    async def mark_item_shown_global(self, *, item_id: int) -> None:
        await self.conn.execute(
            """
            INSERT INTO vocab_item_exposure(item_id, shown_count, last_shown_at, updated_at)
            VALUES (?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(item_id) DO UPDATE SET
                shown_count = shown_count + 1,
                last_shown_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            """,
            (item_id,),
        )
        await self.conn.commit()

    async def get_item_exposure_stats(self, *, item_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            """
            SELECT item_id, shown_count, answered_count, correct_count, last_shown_at, last_answered_at
            FROM vocab_item_exposure
            WHERE item_id = ?
            """,
            (item_id,),
        )
        return await cursor.fetchone()

    async def mark_item_answered_global(self, *, item_id: int, is_correct: bool) -> None:
        await self.conn.execute(
            """
            INSERT INTO vocab_item_exposure(
                item_id, shown_count, answered_count, correct_count, last_answered_at, updated_at
            )
            VALUES (?, 0, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(item_id) DO UPDATE SET
                answered_count = answered_count + 1,
                correct_count = correct_count + ?,
                last_answered_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            """,
            (item_id, 1 if is_correct else 0, 1 if is_correct else 0),
        )
        await self.conn.commit()

    async def seed_demo_items_if_empty(self) -> None:
        cursor = await self.conn.execute("SELECT COUNT(*) AS n FROM vocab_items")
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("vocab_items_count_failed")
        if int(row["n"]) > 0:
            return

        items = [
            ("casa", "Что значит это слово?\n\ncasa", "дом", "noun", "A1", 300, "1K", "home"),
            ("comer", "Что значит это слово?\n\ncomer", "есть", "verb", "A1", 450, "1K", "food"),
            ("rápido", "Что значит это слово?\n\nrápido", "быстрый", "adjective", "A1", 900, "1K", "basic"),
            ("livro", "Что значит это слово?\n\nlivro", "книга", "noun", "A1", 520, "1K", "study"),
            ("água", "Что значит это слово?\n\nágua", "вода", "noun", "A1", 280, "1K", "basic"),
            ("trabalhar", "Что значит это слово?\n\ntrabalhar", "работать", "verb", "A1", 980, "1K", "work"),
            ("abrir", "Что значит это слово?\n\nabrir", "открывать", "verb", "A1", 1100, "2K", "basic"),
            ("feliz", "Что значит это слово?\n\nfeliz", "счастливый", "adjective", "A1", 1300, "2K", "emotion"),
            ("pequeno", "Что значит это слово?\n\npequeno", "маленький", "adjective", "A1", 1400, "2K", "basic"),
            ("ontem", "Что значит это слово?\n\nontem", "вчера", "adverb", "A1", 1500, "2K", "time"),
            ("janela", "Что значит это слово?\n\njanela", "окно", "noun", "A2", 1700, "2K", "home"),
            ("escrever", "Что значит это слово?\n\nescrever", "писать", "verb", "A2", 2200, "5K", "study"),
            ("difícil", "Что значит это слово?\n\ndifícil", "трудный", "adjective", "A2", 2400, "5K", "study"),
            ("cedo", "Что значит это слово?\n\ncedo", "рано", "adverb", "A2", 2600, "5K", "time"),
            ("estrada", "Что значит это слово?\n\nestrada", "дорога", "noun", "B1", 3200, "5K", "travel"),
            ("escolher", "Что значит это слово?\n\nescolher", "выбирать", "verb", "B1", 3600, "5K", "decision"),
            ("estranho", "Что значит это слово?\n\nestranho", "странный", "adjective", "B1", 4200, "5K", "emotion"),
            ("talvez", "Что значит это слово?\n\ntalvez", "возможно", "adverb", "B1", 4700, "5K", "logic"),
        ]

        demo_choices_map: dict[str, list[tuple[str, int, int]]] = {
            "casa": [
                ("дом", 1, 1), ("машина", 0, 2), ("улица", 0, 3), ("окно", 0, 4), ("стол", 0, 5), ("яблоко", 0, 6),
            ],
            "comer": [
                ("спать", 0, 1), ("есть", 1, 2), ("открывать", 0, 3), ("писать", 0, 4), ("читать", 0, 5), ("бежать", 0, 6),
            ],
            "rápido": [
                ("холодный", 0, 1), ("тёмный", 0, 2), ("быстрый", 1, 3), ("мягкий", 0, 4), ("узкий", 0, 5), ("длинный", 0, 6),
            ],
            "livro": [
                ("река", 0, 1), ("чашка", 0, 2), ("дверь", 0, 3), ("книга", 1, 4), ("стена", 0, 5), ("песня", 0, 6),
            ],
            "água": [
                ("огонь", 0, 1), ("камень", 0, 2), ("облако", 0, 3), ("письмо", 0, 4), ("вода", 1, 5), ("мост", 0, 6),
            ],
            "trabalhar": [
                ("танцевать", 0, 1), ("плавать", 0, 2), ("кричать", 0, 3), ("терять", 0, 4), ("рисовать", 0, 5), ("работать", 1, 6),
            ],
            "abrir": [
                ("открывать", 1, 1), ("ломать", 0, 2), ("закрывать", 0, 3), ("толкать", 0, 4), ("искать", 0, 5), ("нести", 0, 6),
            ],
            "feliz": [
                ("грязный", 0, 1), ("счастливый", 1, 2), ("мокрый", 0, 3), ("поздний", 0, 4), ("солёный", 0, 5), ("острый", 0, 6),
            ],
            "pequeno": [
                ("высокий", 0, 1), ("широкий", 0, 2), ("маленький", 1, 3), ("редкий", 0, 4), ("тихий", 0, 5), ("сладкий", 0, 6),
            ],
            "ontem": [
                ("завтра", 0, 1), ("иногда", 0, 2), ("рядом", 0, 3), ("вчера", 1, 4), ("вместе", 0, 5), ("далеко", 0, 6),
            ],
            "janela": [
                ("крыша", 0, 1), ("ручка", 0, 2), ("лампа", 0, 3), ("площадь", 0, 4), ("окно", 1, 5), ("сад", 0, 6),
            ],
            "escrever": [
                ("резать", 0, 1), ("забывать", 0, 2), ("готовить", 0, 3), ("ловить", 0, 4), ("объяснять", 0, 5), ("писать", 1, 6),
            ],
            "difícil": [
                ("трудный", 1, 1), ("свежий", 0, 2), ("гладкий", 0, 3), ("сухой", 0, 4), ("бедный", 0, 5), ("толстый", 0, 6),
            ],
            "cedo": [
                ("медленно", 0, 1), ("рано", 1, 2), ("случайно", 0, 3), ("громко", 0, 4), ("молча", 0, 5), ("снова", 0, 6),
            ],
            "estrada": [
                ("тетрадь", 0, 1), ("скатерть", 0, 2), ("дорога", 1, 3), ("подушка", 0, 4), ("бутылка", 0, 5), ("лестница", 0, 6),
            ],
            "escolher": [
                ("прятать", 0, 1), ("держать", 0, 2), ("спускать", 0, 3), ("выбирать", 1, 4), ("обещать", 0, 5), ("звонить", 0, 6),
            ],
            "estranho": [
                ("честный", 0, 1), ("густой", 0, 2), ("пустой", 0, 3), ("ровный", 0, 4), ("странный", 1, 5), ("сильный", 0, 6),
            ],
            "talvez": [
                ("конечно", 0, 1), ("слева", 0, 2), ("уже", 0, 3), ("никогда", 0, 4), ("затем", 0, 5), ("возможно", 1, 6),
            ],
        }
        for lemma, question_text, correct_answer, pos, level, freq_rank, bin_name, topic_tag in items:
            cursor = await self.conn.execute(
                """
                INSERT INTO vocab_items (
                    lemma, question_text, correct_answer, pos, level, freq_rank, bin_name, topic_tag, is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (lemma, question_text, correct_answer, pos, level, freq_rank, bin_name, topic_tag),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("demo_vocab_item_insert_failed")

            item_id = int(cursor.lastrowid)

            choices = demo_choices_map[lemma]

            for choice_text, is_correct, position_index in choices:
                await self.conn.execute(
                    """
                    INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index)
                    VALUES (?, ?, ?, ?)
                    """,
                    (item_id, choice_text, is_correct, position_index),
                )

        await self.conn.commit()

    async def get_recent_attempt_item_ids(
        self,
        *,
        attempt_id: int,
        previous_attempts_limit: int = 1,
    ) -> list[int]:
        cursor = await self.conn.execute(
            """
            SELECT DISTINCT va.item_id
            FROM vocab_answers va
            WHERE va.attempt_id IN (
                SELECT prev.id
                FROM vocab_attempts prev
                WHERE prev.user_id = (
                    SELECT user_id
                    FROM vocab_attempts
                    WHERE id = ?
                )
                  AND prev.id < ?
                  AND EXISTS (
                      SELECT 1
                      FROM vocab_answers va2
                      WHERE va2.attempt_id = prev.id
                  )
                ORDER BY prev.id DESC
                LIMIT ?
            )
            ORDER BY va.item_id ASC
            """,
            (attempt_id, attempt_id, previous_attempts_limit),
        )
        rows = await cursor.fetchall()
        return [int(row["item_id"]) for row in rows if row["item_id"] is not None]


    async def get_selector_state(self, *, attempt_id: int) -> SelectorRuntimeState:
        cursor = await self.conn.execute(
            """
            SELECT
                shown_item_ids_json,
                pos_counters_json,
                cefr_counters_json,
                bin_counters_json,
                current_item_meta_json
            FROM vocab_selector_state
            WHERE attempt_id = ?
            """,
            (attempt_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("selector_state_not_found")

        return SelectorRuntimeState(
            shown_item_ids=list(json.loads(row["shown_item_ids_json"] or "[]")),
            pos_counters=dict(json.loads(row["pos_counters_json"] or "{}")),
            cefr_counters=dict(json.loads(row["cefr_counters_json"] or "{}")),
            bin_counters=dict(json.loads(row["bin_counters_json"] or "{}")),
            current_item_meta=dict(json.loads(row["current_item_meta_json"] or "{}")),
        )

    async def save_selector_state(self, *, attempt_id: int, state: SelectorRuntimeState) -> None:
        await self.conn.execute(
            """
            UPDATE vocab_selector_state
            SET
                shown_item_ids_json = ?,
                pos_counters_json = ?,
                cefr_counters_json = ?,
                bin_counters_json = ?,
                current_item_meta_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE attempt_id = ?
            """,
            (
                json.dumps(state.shown_item_ids, ensure_ascii=False),
                json.dumps(state.pos_counters, ensure_ascii=False),
                json.dumps(state.cefr_counters, ensure_ascii=False),
                json.dumps(state.bin_counters, ensure_ascii=False),
                json.dumps(state.current_item_meta, ensure_ascii=False),
                attempt_id,
            ),
        )
        await self.conn.commit()


    async def update_selector_state(
        self,
        *,
        attempt_id: int,
        payload: dict[str, object],
    ) -> None:
        await self.conn.execute(
            """
            UPDATE vocab_selector_state
            SET
                selector_payload_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE attempt_id = ?
            """,
            (json.dumps(payload, ensure_ascii=False), attempt_id),
        )
        await self.conn.commit()

    async def get_selector_payload_state(self, *, attempt_id: int) -> dict[str, object]:
        cursor = await self.conn.execute(
            """
            SELECT selector_payload_json
            FROM vocab_selector_state
            WHERE attempt_id = ?
            """,
            (attempt_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("selector_state_not_found")
        raw = row["selector_payload_json"] or "{}"
        return dict(json.loads(raw))

    async def get_choice_with_item(self, *, choice_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            """
            SELECT
                vc.id AS choice_id,
                vc.item_id AS item_id,
                vc.choice_text AS choice_text,
                vc.is_correct AS is_correct,
                vi.correct_answer AS correct_answer,
                vi.lemma AS lemma,
                vi.pos AS pos,
                vi.level AS level,
                vi.bin_name AS bin_name,
                vi.freq_rank AS freq_rank
            FROM vocab_choices vc
            JOIN vocab_items vi ON vi.id = vc.item_id
            WHERE vc.id = ?
            """,
            (choice_id,),
        )
        return await cursor.fetchone()

    async def insert_answer(
        self,
        *,
        attempt_id: int,
        item_id: int,
        selected_choice_id: int | None,
        answer_status: str,
        answer_kind: str = "selected",
        is_correct: bool,
        shown_at: str | None = None,
        answered_at: str | None = None,
        latency_ms: int | None = None,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO vocab_answers (
                attempt_id, item_id, selected_choice_id, answer_status, answer_kind,
                is_correct, shown_at, answered_at, latency_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                item_id,
                selected_choice_id,
                answer_status,
                answer_kind,
                int(is_correct),
                shown_at,
                answered_at,
                latency_ms,
            ),
        )
        await self.conn.commit()

    async def bump_attempt_after_answer(
        self,
        *,
        attempt_id: int,
        is_correct: bool,
        is_dont_know: bool,
    ) -> None:
        await self.conn.execute(
            """
            UPDATE vocab_attempts
            SET
                questions_answered = questions_answered + 1,
                correct_count = correct_count + ?,
                dont_know_count = dont_know_count + ?,
                current_step = current_step + 1,
                hard_reject_streak = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                1 if is_correct else 0,
                1 if is_dont_know else 0,
                attempt_id,
            ),
        )
        await self.conn.commit()

    async def bump_attempt_reject(
        self,
        *,
        attempt_id: int,
    ) -> None:
        await self.conn.execute(
            """
            UPDATE vocab_attempts
            SET
                total_reject_count = total_reject_count + 1,
                hard_reject_streak = hard_reject_streak + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (attempt_id,),
        )
        await self.conn.commit()

    async def get_item_by_id(self, *, item_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            """
            SELECT id, lemma, question_text, correct_answer, pos, level, bin_name, freq_rank
            FROM vocab_items
            WHERE id = ?
            """,
            (item_id,),
        )
        return await cursor.fetchone()

    async def get_choices_for_item(self, *, item_id: int) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT id, choice_text, is_correct, position_index
            FROM vocab_choices
            WHERE item_id = ?
            ORDER BY position_index
            """,
            (item_id,),
        )
        rows = await cursor.fetchall()
        return list(rows)

    async def get_attempt_stats(self, *, attempt_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            """
            SELECT
                id,
                question_limit,
                questions_answered,
                correct_count,
                dont_know_count,
                total_reject_count,
                hard_reject_streak,
                status
            FROM vocab_attempts
            WHERE id = ?
            """,
            (attempt_id,),
        )
        return await cursor.fetchone()


    async def count_remaining_items(self, *, attempt_id: int) -> int:
        cursor = await self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM vocab_items vi
            WHERE vi.is_active = 1
              AND vi.id NOT IN (
                  SELECT item_id
                  FROM vocab_answers
                  WHERE attempt_id = ?
              )
            """,
            (attempt_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("remaining_items_count_failed")
        return int(row["n"])


    async def get_scoring_rows(self, *, attempt_id: int) -> list[dict[str, object]]:
        cursor = await self.conn.execute(
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
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_attempt_answer_stats(self, *, attempt_id: int) -> dict[str, int]:
        cursor = await self.conn.execute(
            """
            SELECT
                COUNT(*) AS total_answers,
                COALESCE(SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END), 0) AS correct_answers
            FROM vocab_answers
            WHERE attempt_id = ?
            """,
            (attempt_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("attempt_answer_stats_failed")
        return {
            "total_answers": int(row["total_answers"]),
            "correct_answers": int(row["correct_answers"]),
        }


    async def increment_attempt_step(self, *, attempt_id: int) -> None:
        await self.conn.execute(
            """
            UPDATE vocab_attempts
            SET current_step = current_step + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (attempt_id,),
        )
        await self.conn.commit()

    async def abort_vocab_attempt(
        self,
        *,
        vocab_attempt_id: int,
        mode_run_id: int,
        completion_reason: str,
    ) -> None:
        await self.conn.execute(
            """
            UPDATE vocab_attempts
            SET status = 'aborted',
                aborted_at = CURRENT_TIMESTAMP,
                completion_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (completion_reason, vocab_attempt_id),
        )
        await self.conn.execute(
            """
            UPDATE mode_runs
            SET status = 'aborted',
                aborted_at = CURRENT_TIMESTAMP,
                completion_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (completion_reason, mode_run_id),
        )
        await self.conn.commit()

    async def finish_vocab_attempt(
        self,
        *,
        vocab_attempt_id: int,
        mode_run_id: int,
        estimated_vocab_band: str,
        estimated_vocab_size: int,
        confidence: float,
        completion_reason: str,
    ) -> None:
        payload = json.dumps(
            {
                "estimated_vocab_band": estimated_vocab_band,
                "estimated_vocab_size": estimated_vocab_size,
                "confidence": confidence,
                "completion_reason": completion_reason,
            },
            ensure_ascii=False,
        )

        await self.conn.execute(
            """
            UPDATE vocab_attempts
            SET status = 'finished',
                finished_at = CURRENT_TIMESTAMP,
                estimated_vocab_band = ?,
                estimated_vocab_size = ?,
                confidence = ?,
                completion_reason = ?,
                vocab_estimate = ?,
                cefr_estimate = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                estimated_vocab_band,
                estimated_vocab_size,
                confidence,
                completion_reason,
                estimated_vocab_size,
                estimated_vocab_band,
                vocab_attempt_id,
            ),
        )
        await self.conn.execute(
            """
            UPDATE mode_runs
            SET status = 'finished',
                finished_at = CURRENT_TIMESTAMP,
                result_payload_json = ?,
                completion_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload, completion_reason, mode_run_id),
        )
        await self.conn.commit()

    async def persist_mode_result_stub(
        self,
        *,
        mode_run_id: int,
        user_id: int,
        completion_reason: str,
    ) -> None:
        await self.conn.execute(
            """
            INSERT OR REPLACE INTO mode_results (
                mode, run_id, user_id, result_version, score_numeric, band_text, cefr_level,
                confidence, result_payload_json, created_at
            )
            VALUES (?, ?, ?, 'v1', NULL, NULL, NULL, NULL, ?, CURRENT_TIMESTAMP)
            """,
            (
                ModeCode.VOCAB.value,
                mode_run_id,
                user_id,
                json.dumps({"completion_reason": completion_reason}, ensure_ascii=False),
            ),
        )
        await self.conn.commit()

    async def persist_mode_result_final(
        self,
        *,
        mode_run_id: int,
        user_id: int,
        estimated_vocab_band: str,
        estimated_vocab_size: int,
        confidence: float,
        completion_reason: str,
    ) -> None:
        await self.conn.execute(
            """
            INSERT OR REPLACE INTO mode_results (
                mode, run_id, user_id, result_version, score_numeric, band_text, cefr_level,
                confidence, result_payload_json, created_at
            )
            VALUES (?, ?, ?, 'v1', ?, ?, NULL, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                ModeCode.VOCAB.value,
                mode_run_id,
                user_id,
                float(estimated_vocab_size),
                estimated_vocab_band,
                confidence,
                json.dumps(
                    {
                        "estimated_vocab_band": estimated_vocab_band,
                        "estimated_vocab_size": estimated_vocab_size,
                        "confidence": confidence,
                        "completion_reason": completion_reason,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        await self.conn.commit()

    async def upsert_user_mode_priors(
        self,
        *,
        user_id: int,
        mode_run_id: int,
        estimated_vocab_band: str,
        confidence: float,
        recommended_level_start_band: str,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO user_mode_priors (
                user_id,
                last_vocab_run_id,
                last_vocab_band,
                vocab_confidence,
                recommended_level_start_band,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                last_vocab_run_id = excluded.last_vocab_run_id,
                last_vocab_band = excluded.last_vocab_band,
                vocab_confidence = excluded.vocab_confidence,
                recommended_level_start_band = excluded.recommended_level_start_band,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                mode_run_id,
                estimated_vocab_band,
                confidence,
                recommended_level_start_band,
            ),
        )
        await self.conn.commit()

    async def insert_result_snapshot(
        self,
        *,
        attempt_id: int,
        step_index: int,
        payload: dict[str, object],
    ) -> None:
        estimated_vocab_band = payload.get("estimated_vocab_band")
        estimated_vocab_size = payload.get("estimated_vocab_size")
        confidence = payload.get("confidence")

        await self.conn.execute(
            """
            INSERT INTO vocab_result_snapshots (
                attempt_id, step_index, estimated_vocab_band, estimated_vocab_size, confidence, snapshot_payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                step_index,
                estimated_vocab_band,
                estimated_vocab_size,
                confidence,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        await self.conn.commit()


    async def get_active_user_mode_baseline(
        self,
        *,
        user_id: int,
        mode: str,
    ) -> dict | None:
        if not await self._table_exists("user_mode_baselines"):
            return None

        cur = await self.conn.execute(
            """
            SELECT *
            FROM user_mode_baselines
            WHERE user_id = ?
              AND mode = ?
              AND is_active = 1
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, mode),
        )
        row = await cur.fetchone()
        if row is None:
            return None

        out = dict(row)
        payload = out.get("calibration_payload_json")
        if payload:
            try:
                out["calibration_payload_json"] = json.loads(payload)
            except Exception:
                pass
        return out

    async def upsert_user_vocab_baseline(
        self,
        *,
        user_id: int,
        mode_run_id: int,
        attempt_id: int,
        estimated_vocab_band: str,
        estimated_vocab_size: int,
        confidence: float,
        correct_answers: int,
        total_answers: int,
    ) -> None:
        if not await self._table_exists("user_mode_baselines"):
            return

        has_progress_events = await self._table_exists("user_progress_events")

        previous = await self.get_active_user_mode_baseline(
            user_id=user_id,
            mode="vocab",
        )

        previous_payload = None
        if previous is not None:
            raw = previous.get("calibration_payload_json")
            if isinstance(raw, dict):
                previous_payload = raw
            else:
                previous_payload = {
                    "estimated_vocab_band": previous.get("estimated_vocab_band"),
                    "estimated_vocab_size": previous.get("estimated_vocab_size"),
                    "confidence": previous.get("confidence"),
                }

        size = int(estimated_vocab_size or 0)
        if size < 1000:
            estimated_cefr_level = "A1"
        elif size < 2500:
            estimated_cefr_level = "A2"
        elif size < 4000:
            estimated_cefr_level = "B1"
        elif size < 7000:
            estimated_cefr_level = "B2"
        else:
            estimated_cefr_level = "C1"

        current_payload = {
            "mode": "vocab",
            "estimated_vocab_size": int(estimated_vocab_size or 0),
            "estimated_vocab_band": str(estimated_vocab_band or ""),
            "estimated_cefr_level": estimated_cefr_level,
            "confidence": float(confidence or 0),
            "question_count": int(total_answers or 0),
            "correct_answers": int(correct_answers or 0),
            "calibration_hint": {
                "level_entry_cefr_guess": estimated_cefr_level,
                "recommended_level_start_band": str(estimated_vocab_band or ""),
            },
        }

        event_type = "baseline_created"
        delta_payload = {
            "previous_vocab_size": None,
            "current_vocab_size": int(estimated_vocab_size or 0),
            "delta_vocab_size": None,
            "previous_vocab_band": None,
            "current_vocab_band": str(estimated_vocab_band or ""),
        }

        if previous_payload is not None:
            prev_band = str(previous_payload.get("estimated_vocab_band") or "")
            prev_size = int(previous_payload.get("estimated_vocab_size") or 0)
            curr_band = str(estimated_vocab_band or "")
            curr_size = int(estimated_vocab_size or 0)

            order = {
                "<1.5k": 1,
                "1.5k-2.5k": 2,
                "2.5k-4k": 3,
                "4k-6k": 4,
                "6k-8k": 5,
                "8k+": 6,
            }
            delta_size = curr_size - prev_size

            if curr_band != prev_band:
                if order.get(curr_band, 0) > order.get(prev_band, 0):
                    event_type = "result_improved"
                elif order.get(curr_band, 0) < order.get(prev_band, 0):
                    event_type = "result_declined"
                else:
                    event_type = "result_stable"
            else:
                if delta_size >= 400:
                    event_type = "result_improved"
                elif delta_size <= -400:
                    event_type = "result_declined"
                else:
                    event_type = "result_stable"

            delta_payload = {
                "previous_vocab_size": prev_size,
                "current_vocab_size": curr_size,
                "delta_vocab_size": delta_size,
                "previous_vocab_band": prev_band,
                "current_vocab_band": curr_band,
            }

        if previous is not None:
            await self.conn.execute(
                """
                UPDATE user_mode_baselines
                SET is_active = 0,
                    valid_until = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (int(previous["id"]),),
            )

        await self.conn.execute(
            """
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
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                "vocab",
                "vocab_baseline_v1",
                "vocab",
                mode_run_id,
                attempt_id,
                int(estimated_vocab_size or 0),
                str(estimated_vocab_band or ""),
                estimated_cefr_level,
                float(confidence or 0),
                json.dumps(current_payload, ensure_ascii=False),
            ),
        )

        if has_progress_events:
            await self.conn.execute(
                """
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
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    user_id,
                    "vocab",
                    mode_run_id,
                    attempt_id,
                    event_type,
                    json.dumps(previous_payload, ensure_ascii=False) if previous_payload is not None else None,
                    json.dumps(current_payload, ensure_ascii=False),
                    json.dumps(delta_payload, ensure_ascii=False),
                ),
            )

        await self.conn.commit()
