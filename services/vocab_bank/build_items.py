from __future__ import annotations

import sqlite3


def assign_bin_name(freq_rank: int | None) -> str:
    if freq_rank is None:
        return "rare"
    if freq_rank <= 1000:
        return "1K"
    if freq_rank <= 2000:
        return "2K"
    if freq_rank <= 5000:
        return "5K"
    if freq_rank <= 10000:
        return "10K"
    if freq_rank <= 20000:
        return "20K"
    return "rare"


def build_vocab_items_from_candidates(
    conn: sqlite3.Connection,
    *,
    source_name: str | None = None,
    truncate_topic_prefix: str | None = None,
) -> int:
    conn.row_factory = sqlite3.Row

    sql = """
    SELECT
        id,
        source_name,
        normalized_lemma,
        lemma_key,
        pos,
        level,
        freq_rank,
        ru_gloss,
        gloss_key,
        is_eligible,
        reject_reason,
        merge_group_id
    FROM vocab_lemma_candidates
    WHERE is_eligible = 1
    """
    params: tuple[object, ...] = ()
    if source_name:
        sql += " AND source_name = ?"
        params = (source_name,)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return 0

    if truncate_topic_prefix:
        conn.execute(
            "DELETE FROM vocab_items WHERE topic_tag LIKE ?",
            (f"{truncate_topic_prefix}%",),
        )

    inserted = 0
    seen_keys: set[tuple[str, str]] = set()

    for row in rows:
        lemma = str(row["normalized_lemma"]).strip()
        pos = str(row["pos"]).strip() if row["pos"] is not None else ""
        key = (lemma, pos)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        freq_rank = int(row["freq_rank"]) if row["freq_rank"] is not None else None
        bin_name = assign_bin_name(freq_rank)

        conn.execute(
            """
            INSERT INTO vocab_items (
                lemma,
                question_text,
                correct_answer,
                pos,
                level,
                freq_rank,
                bin_name,
                topic_tag,
                is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                lemma,
                lemma,
                row["ru_gloss"],
                row["pos"],
                row["level"],
                freq_rank,
                bin_name,
                f"build:{row['source_name']}",
            ),
        )
        inserted += 1

    conn.commit()
    return inserted
