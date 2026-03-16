#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

DB_PATH = Path("data/lingua_staging.db")
OUT_DIR = Path("tmp/2k_adjectives_review")
CSV_PATH = OUT_DIR / "staging_2k_adjectives_review.csv"
JSON_PATH = OUT_DIR / "staging_2k_adjectives_review.json"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
          vi.id,
          vi.lemma,
          vi.correct_answer,
          vi.freq_rank,
          vi.is_active,
          vi.topic_tag,
          SUM(CASE WHEN vc.id IS NOT NULL THEN 1 ELSE 0 END) AS choice_count,
          SUM(CASE WHEN COALESCE(vc.is_correct,0)=1 THEN 1 ELSE 0 END) AS correct_count
        FROM vocab_items vi
        LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.pos = 'adjective'
          AND vi.bin_name = '2K'
        GROUP BY vi.id, vi.lemma, vi.correct_answer, vi.freq_rank, vi.is_active, vi.topic_tag
        ORDER BY vi.freq_rank DESC, vi.lemma ASC, vi.id ASC
        """
    ).fetchall()

    items = []
    for r in rows:
        choice_rows = conn.execute(
            """
            SELECT id, choice_text, is_correct, position_index
            FROM vocab_choices
            WHERE item_id = ?
            ORDER BY position_index ASC, id ASC
            """,
            (r["id"],),
        ).fetchall()

        choices_joined = " | ".join(
            f"{'*' if int(c['is_correct'] or 0) == 1 else '-'} {c['choice_text']}"
            for c in choice_rows
        )

        items.append({
            "id": int(r["id"]),
            "lemma": str(r["lemma"]),
            "correct_answer": str(r["correct_answer"]),
            "freq_rank": int(r["freq_rank"]) if r["freq_rank"] is not None else None,
            "is_active": int(r["is_active"] or 0),
            "choice_count": int(r["choice_count"] or 0),
            "correct_count": int(r["correct_count"] or 0),
            "topic_tag": str(r["topic_tag"]) if r["topic_tag"] is not None else "",
            "choices_joined": choices_joined,
        })

    dup_rows = conn.execute(
        """
        SELECT LOWER(TRIM(lemma)) AS lemma_key, COUNT(*) AS n
        FROM vocab_items
        WHERE pos = 'adjective'
          AND bin_name = '2K'
        GROUP BY LOWER(TRIM(lemma))
        HAVING COUNT(*) > 1
        ORDER BY lemma_key
        """
    ).fetchall()

    duplicates = []
    for d in dup_rows:
        lemma_key = str(d["lemma_key"])
        grp = conn.execute(
            """
            SELECT
              vi.id,
              vi.lemma,
              vi.correct_answer,
              vi.freq_rank,
              vi.is_active,
              vi.topic_tag,
              SUM(CASE WHEN vc.id IS NOT NULL THEN 1 ELSE 0 END) AS choice_count,
              SUM(CASE WHEN COALESCE(vc.is_correct,0)=1 THEN 1 ELSE 0 END) AS correct_count
            FROM vocab_items vi
            LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
            WHERE vi.pos = 'adjective'
              AND vi.bin_name = '2K'
              AND LOWER(TRIM(vi.lemma)) = ?
            GROUP BY vi.id, vi.lemma, vi.correct_answer, vi.freq_rank, vi.is_active, vi.topic_tag
            ORDER BY vi.is_active DESC, vi.freq_rank DESC, vi.id ASC
            """,
            (lemma_key,),
        ).fetchall()

        duplicates.append({
            "lemma_key": lemma_key,
            "rows": [
                {
                    "id": int(x["id"]),
                    "lemma": str(x["lemma"]),
                    "correct_answer": str(x["correct_answer"]),
                    "freq_rank": int(x["freq_rank"]) if x["freq_rank"] is not None else None,
                    "is_active": int(x["is_active"] or 0),
                    "choice_count": int(x["choice_count"] or 0),
                    "correct_count": int(x["correct_count"] or 0),
                    "topic_tag": str(x["topic_tag"]) if x["topic_tag"] is not None else "",
                }
                for x in grp
            ]
        })

    summary = {
        "count": len(items),
        "active_count": sum(1 for x in items if x["is_active"] == 1),
        "valid_6_1_count": sum(1 for x in items if x["choice_count"] == 6 and x["correct_count"] == 1),
        "duplicates_count": len(duplicates),
        "csv_path": str(CSV_PATH),
        "json_path": str(JSON_PATH),
    }

    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id", "lemma", "correct_answer", "freq_rank", "is_active",
                "choice_count", "correct_count", "topic_tag", "choices_joined",
            ],
        )
        writer.writeheader()
        writer.writerows(items)

    JSON_PATH.write_text(
        json.dumps({"summary": summary, "items": items, "duplicates": duplicates}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("===== STAGING 2K ADJECTIVES SUMMARY =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n===== STAGING 2K ADJECTIVES CSV PREVIEW =====")
    for row in items[:80]:
        print(row)

    print("\n===== DUPLICATES =====")
    for grp in duplicates:
        print(json.dumps(grp, ensure_ascii=False))

    conn.close()


if __name__ == "__main__":
    main()
