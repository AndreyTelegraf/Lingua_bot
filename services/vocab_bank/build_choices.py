from __future__ import annotations

import random
import sqlite3
from collections import Counter


def _norm_text(value: str | None) -> str:
    return (value or "").strip().casefold()


def _fetch_target_items(conn: sqlite3.Connection, *, topic_tag_prefix: str | None) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    sql = """
    SELECT id, lemma, correct_answer, pos, level, freq_rank, bin_name, topic_tag
    FROM vocab_items
    WHERE topic_tag LIKE 'build:%'
    """
    params: tuple[object, ...] = ()
    if topic_tag_prefix:
        sql += " AND topic_tag LIKE ?"
        params = (f"{topic_tag_prefix}%",)
    sql += " ORDER BY id"
    return conn.execute(sql, params).fetchall()


def _reuse_cap_for_pos(pos: str) -> int:
    pos = (pos or "").strip()
    if pos == "adjective":
        return 4
    if pos == "adverb":
        return 6
    if pos == "verb":
        return 8
    if pos == "noun":
        return 8
    return 6


def _fetch_pool(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        """
        SELECT id, lemma, correct_answer, pos, level, freq_rank, bin_name, topic_tag
        FROM vocab_items
        WHERE topic_tag LIKE 'build:%'
        ORDER BY id
        """
    ).fetchall()


def _pick_distractors(item: sqlite3.Row, pool: list[sqlite3.Row], *, needed: int = 5, distractor_usage: Counter[tuple[str, str]]) -> list[sqlite3.Row]:
    item_id = int(item["id"])
    correct = str(item["correct_answer"] or "")
    item_pos = str(item["pos"] or "").strip()

    seen: set[str] = {_norm_text(correct)}
    candidates: list[sqlite3.Row] = []

    reuse_cap = _reuse_cap_for_pos(item_pos)

    for row in pool:
        if int(row["id"]) == item_id:
            continue
        if str(row["pos"] or "").strip() != item_pos:
            continue

        cand = str(row["correct_answer"] or "")
        cand_norm = _norm_text(cand)
        if not cand_norm or cand_norm in seen:
            continue
        if distractor_usage[(item_pos, cand_norm)] >= reuse_cap:
            continue

        seen.add(cand_norm)
        candidates.append(row)

    ranked = sorted(
        candidates,
        key=lambda row: (
            distractor_usage[(str(row["pos"] or "").strip(), _norm_text(str(row["correct_answer"] or "")))],
            int(row["id"]),
        ),
    )
    return ranked[:needed]


def _deterministic_shuffle_choices(item_id: int, choices: list[str]) -> list[str]:
    rnd = random.Random(item_id)
    out = list(choices)
    rnd.shuffle(out)
    return out


def build_vocab_choices_for_items(
    conn: sqlite3.Connection,
    *,
    topic_tag_prefix: str | None = None,
    truncate_existing: bool = False,
) -> int:
    conn.row_factory = sqlite3.Row

    items = _fetch_target_items(conn, topic_tag_prefix=topic_tag_prefix)
    if not items:
        return 0

    if truncate_existing:
        item_ids = [int(r["id"]) for r in items]
        conn.executemany(
            "DELETE FROM vocab_choices WHERE item_id = ?",
            [(item_id,) for item_id in item_ids],
        )

    pool = _fetch_pool(conn)
    distractor_usage: Counter[tuple[str, str]] = Counter()
    inserted_items = 0

    for item in items:
        item_id = int(item["id"])
        existing_n = conn.execute(
            "SELECT COUNT(*) AS n FROM vocab_choices WHERE item_id = ?",
            (item_id,),
        ).fetchone()["n"]
        if int(existing_n) > 0:
            continue

        correct = str(item["correct_answer"])
        distractor_rows = _pick_distractors(item, pool, needed=5, distractor_usage=distractor_usage)
        if len(distractor_rows) < 5:
            continue

        distractors = [str(row["correct_answer"] or "") for row in distractor_rows[:5]]
        ordered = _deterministic_shuffle_choices(item_id, [correct] + distractors)

        correct_seen = 0
        for idx, choice_text in enumerate(ordered, start=1):
            is_correct = 1 if _norm_text(choice_text) == _norm_text(correct) else 0
            correct_seen += is_correct
            conn.execute(
                """
                INSERT INTO vocab_choices (
                    item_id,
                    choice_text,
                    is_correct,
                    position_index
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    item_id,
                    choice_text,
                    is_correct,
                    idx,
                ),
            )

        if correct_seen != 1:
            raise RuntimeError(f"invalid_correct_count_after_shuffle:{item_id}:{correct_seen}")

        for row in distractor_rows[:5]:
            distractor_usage[(str(row["pos"] or "").strip(), _norm_text(str(row["correct_answer"] or "")))] += 1

        inserted_items += 1

    conn.commit()
    return inserted_items
