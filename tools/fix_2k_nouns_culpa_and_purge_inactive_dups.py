#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

DB_PATH = Path("data/lingua_staging.db")
BACKUP_DIR = Path("tmp/db_backups")
REPORT_PATH = Path("tmp/fix_2k_nouns_culpa_and_purge_inactive_dups_report.json")

TARGET_LEMMA = "culpa"
NEW_TRANSLATION = "вина"

def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

def fetch_item(conn: sqlite3.Connection, item_id: int) -> dict:
    row = conn.execute(
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
          SUM(CASE WHEN COALESCE(vc.is_correct,0)=1 THEN 1 ELSE 0 END) AS correct_count
        FROM vocab_items vi
        LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.id = ?
        GROUP BY vi.id, vi.lemma, vi.correct_answer, vi.pos, vi.bin_name, vi.freq_rank, vi.is_active, vi.topic_tag
        """,
        (item_id,),
    ).fetchone()
    return dict(row) if row else {}

def fetch_choices(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, choice_text, is_correct, position_index
        FROM vocab_choices
        WHERE item_id = ?
        ORDER BY position_index ASC, id ASC
        """,
        (item_id,),
    ).fetchall()
    return [dict(r) for r in rows]

def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"lingua_staging_before_fix_2k_nouns_culpa_and_purge_{utc_stamp()}.db"
    shutil.copy2(DB_PATH, backup_path)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    target = conn.execute(
        """
        SELECT id
        FROM vocab_items
        WHERE pos = 'noun'
          AND bin_name = '2K'
          AND is_active = 1
          AND lemma = ?
        ORDER BY id ASC
        LIMIT 1
        """,
        (TARGET_LEMMA,),
    ).fetchone()
    if not target:
        raise SystemExit("Active 2K noun target lemma not found: culpa")

    item_id = int(target["id"])
    before_item = fetch_item(conn, item_id)
    before_choices = fetch_choices(conn, item_id)

    correct_choice = conn.execute(
        """
        SELECT id, choice_text
        FROM vocab_choices
        WHERE item_id = ? AND is_correct = 1
        ORDER BY position_index ASC, id ASC
        LIMIT 1
        """,
        (item_id,),
    ).fetchone()
    if not correct_choice:
        raise SystemExit("Correct choice not found for active culpa item")

    conn.execute(
        "UPDATE vocab_items SET correct_answer = ? WHERE id = ?",
        (NEW_TRANSLATION, item_id),
    )
    conn.execute(
        "UPDATE vocab_choices SET choice_text = ? WHERE id = ?",
        (NEW_TRANSLATION, int(correct_choice["id"])),
    )

    fully_inactive_dup_groups = []
    purge_ids: list[int] = []

    dup_keys = conn.execute(
        """
        SELECT LOWER(TRIM(lemma)) AS lemma_key, COUNT(*) AS n
        FROM vocab_items
        WHERE pos = 'noun' AND bin_name = '2K'
        GROUP BY LOWER(TRIM(lemma))
        HAVING COUNT(*) > 1
        ORDER BY lemma_key
        """
    ).fetchall()

    for dk in dup_keys:
        lemma_key = dk["lemma_key"]
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
            WHERE vi.pos = 'noun'
              AND vi.bin_name = '2K'
              AND LOWER(TRIM(vi.lemma)) = ?
            GROUP BY vi.id, vi.lemma, vi.correct_answer, vi.freq_rank, vi.is_active, vi.topic_tag
            ORDER BY vi.id ASC
            """,
            (lemma_key,),
        ).fetchall()
        rows_d = [dict(r) for r in rows]

        if all(int(r["is_active"] or 0) == 0 for r in rows_d):
            fully_inactive_dup_groups.append({
                "lemma_key": lemma_key,
                "rows": rows_d,
            })
            purge_ids.extend(int(r["id"]) for r in rows_d)

    if purge_ids:
        conn.executemany("DELETE FROM vocab_choices WHERE item_id = ?", [(x,) for x in purge_ids])
        conn.executemany("DELETE FROM vocab_items WHERE id = ?", [(x,) for x in purge_ids])

    conn.commit()

    after_item = fetch_item(conn, item_id)
    after_choices = fetch_choices(conn, item_id)

    remaining_dup_groups = conn.execute(
        """
        SELECT COUNT(*)
        FROM (
          SELECT LOWER(TRIM(lemma)) AS lemma_key
          FROM vocab_items
          WHERE pos = 'noun' AND bin_name = '2K'
          GROUP BY LOWER(TRIM(lemma))
          HAVING COUNT(*) > 1
        ) t
        """
    ).fetchone()[0]

    report = {
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "culpa_fix": {
            "item_id": item_id,
            "before_item": before_item,
            "before_choices": before_choices,
            "after_item": after_item,
            "after_choices": after_choices,
        },
        "purged_fully_inactive_duplicate_group_count": len(fully_inactive_dup_groups),
        "purged_fully_inactive_duplicate_item_count": len(purge_ids),
        "purged_groups": fully_inactive_dup_groups,
        "remaining_duplicate_group_count": int(remaining_dup_groups),
    }

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("===== FIX 2K NOUNS CULPA + PURGE FULLY-INACTIVE DUPS =====")
    print(json.dumps({
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "culpa_item_id": item_id,
        "culpa_new_translation": NEW_TRANSLATION,
        "purged_fully_inactive_duplicate_group_count": len(fully_inactive_dup_groups),
        "purged_fully_inactive_duplicate_item_count": len(purge_ids),
        "remaining_duplicate_group_count": int(remaining_dup_groups),
        "report_path": str(REPORT_PATH),
    }, ensure_ascii=False, indent=2))

    print("\n===== CULPA AFTER =====")
    print(json.dumps(after_item, ensure_ascii=False, indent=2))
    print(json.dumps(after_choices, ensure_ascii=False, indent=2))

    conn.close()

if __name__ == "__main__":
    main()
