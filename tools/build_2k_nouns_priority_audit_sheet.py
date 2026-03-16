#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

DB_PATH = Path("data/lingua_staging.db")
OUT_DIR = Path("tmp/2k_nouns_priority_audit")
CSV_PATH = OUT_DIR / "staging_2k_nouns_priority_audit.csv"
JSON_PATH = OUT_DIR / "staging_2k_nouns_priority_audit.json"

SUSPECT_MAP = {
    "culpa": {"изъян"},
}

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
          vi.pos,
          vi.bin_name,
          vi.freq_rank,
          vi.is_active,
          vi.topic_tag,
          SUM(CASE WHEN vc.id IS NOT NULL THEN 1 ELSE 0 END) AS choice_count,
          SUM(CASE WHEN COALESCE(vc.is_correct,0)=1 THEN 1 ELSE 0 END) AS correct_count,
          GROUP_CONCAT(
            CASE WHEN vc.id IS NOT NULL THEN
              CASE WHEN COALESCE(vc.is_correct,0)=1 THEN '* ' ELSE '- ' END || vc.choice_text
            END,
            ' | '
          ) AS choices_joined
        FROM vocab_items vi
        LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.pos = 'noun'
          AND vi.bin_name = '2K'
          AND vi.is_active = 1
        GROUP BY vi.id, vi.lemma, vi.correct_answer, vi.pos, vi.bin_name, vi.freq_rank, vi.is_active, vi.topic_tag
        ORDER BY vi.freq_rank DESC, vi.lemma ASC
        """
    ).fetchall()

    audit_rows = []
    for r in rows:
        d = dict(r)
        tags = []
        lemma = d["lemma"]
        ans = d["correct_answer"]
        if lemma in SUSPECT_MAP and ans in SUSPECT_MAP[lemma]:
            tags.append("SUSPECT_TRANSLATION")
        if tags:
            d["issue_tags"] = "|".join(tags)
            audit_rows.append(d)

    summary = {
        "db_path": str(DB_PATH),
        "total_2k_nouns_active_rows": len(rows),
        "audit_rows": len(audit_rows),
    }

    fieldnames = [
        "id","lemma","correct_answer","pos","bin_name","freq_rank","is_active",
        "choice_count","correct_count","topic_tag","issue_tags","choices_joined"
    ]
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in audit_rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})

    JSON_PATH.write_text(
        json.dumps({"summary": summary, "rows": audit_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("===== STAGING 2K NOUNS PRIORITY AUDIT SUMMARY =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n===== PRIORITY AUDIT ROWS =====")
    for row in audit_rows:
        print(json.dumps(row, ensure_ascii=False))

    conn.close()

if __name__ == "__main__":
    main()
