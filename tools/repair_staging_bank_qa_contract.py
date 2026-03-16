#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/lingua_staging.db")
BACKUP_DIR = Path("tmp/db_backups")
REPORT_PATH = Path("tmp/repair_staging_bank_qa_contract_report.json")


def fetch_bad_choice_items(cur: sqlite3.Cursor) -> list[dict]:
    rows = cur.execute(
        '''
        SELECT
          i.id,
          i.lemma,
          i.pos,
          i.bin_name,
          i.freq_rank,
          COUNT(c.id) AS choice_count,
          SUM(CASE WHEN COALESCE(c.is_correct, 0) = 1 THEN 1 ELSE 0 END) AS correct_count
        FROM vocab_items i
        LEFT JOIN vocab_choices c ON c.item_id = i.id
        WHERE COALESCE(i.is_active, 1) = 1
        GROUP BY i.id, i.lemma, i.pos, i.bin_name, i.freq_rank
        HAVING COUNT(c.id) <> 6
           OR SUM(CASE WHEN COALESCE(c.is_correct, 0) = 1 THEN 1 ELSE 0 END) <> 1
        ORDER BY i.id
        '''
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_duplicate_groups(cur: sqlite3.Cursor) -> list[dict]:
    groups = cur.execute(
        '''
        SELECT
          LOWER(TRIM(lemma)) AS lemma_key,
          LOWER(TRIM(pos)) AS pos_key,
          COUNT(*) AS n
        FROM vocab_items
        WHERE COALESCE(is_active, 1) = 1
        GROUP BY LOWER(TRIM(lemma)), LOWER(TRIM(pos))
        HAVING COUNT(*) > 1
        ORDER BY n DESC, lemma_key, pos_key
        '''
    ).fetchall()

    out = []
    for grp in groups:
        rows = cur.execute(
            '''
            SELECT
              i.id,
              i.lemma,
              i.pos,
              i.bin_name,
              i.freq_rank,
              i.updated_at,
              COUNT(c.id) AS choice_count,
              SUM(CASE WHEN COALESCE(c.is_correct, 0) = 1 THEN 1 ELSE 0 END) AS correct_count
            FROM vocab_items i
            LEFT JOIN vocab_choices c ON c.item_id = i.id
            WHERE COALESCE(i.is_active, 1) = 1
              AND LOWER(TRIM(i.lemma)) = ?
              AND LOWER(TRIM(i.pos)) = ?
            GROUP BY i.id, i.lemma, i.pos, i.bin_name, i.freq_rank, i.updated_at
            ORDER BY i.id
            ''',
            (grp["lemma_key"], grp["pos_key"]),
        ).fetchall()
        out.append(
            {
                "lemma_key": grp["lemma_key"],
                "pos_key": grp["pos_key"],
                "rows": [dict(r) for r in rows],
            }
        )
    return out


def canonical_sort_key(row: dict) -> tuple:
    valid = int((row["choice_count"] or 0) == 6 and (row["correct_count"] or 0) == 1)
    freq = int(row["freq_rank"] or -1)
    item_id = int(row["id"])
    return (-valid, -freq, item_id)


def audit(cur: sqlite3.Cursor) -> dict:
    bad_choice_items = fetch_bad_choice_items(cur)
    dup_groups = fetch_duplicate_groups(cur)
    return {
        "bad_choice_items": bad_choice_items,
        "duplicate_groups": dup_groups,
        "bad_choice_item_count": len(bad_choice_items),
        "duplicate_group_count": len(dup_groups),
    }


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"{DB_PATH.stem}_before_bank_qa_repair_{ts}.db"
    shutil.copy2(DB_PATH, backup_path)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    before = audit(cur)

    deactivated_bad_choice_ids: list[int] = []
    duplicate_keep_ids: list[int] = []
    duplicate_drop_ids: list[int] = []

    cur.execute("BEGIN")

    for row in before["bad_choice_items"]:
        item_id = int(row["id"])
        cur.execute(
            "UPDATE vocab_items SET is_active = 0 WHERE id = ?",
            (item_id,),
        )
        deactivated_bad_choice_ids.append(item_id)

    dup_groups_after_bad_drop = fetch_duplicate_groups(cur)
    for grp in dup_groups_after_bad_drop:
        rows = grp["rows"]
        if len(rows) <= 1:
            continue
        rows_sorted = sorted(rows, key=canonical_sort_key)
        keep_id = int(rows_sorted[0]["id"])
        duplicate_keep_ids.append(keep_id)
        for row in rows_sorted[1:]:
            drop_id = int(row["id"])
            cur.execute(
                "UPDATE vocab_items SET is_active = 0 WHERE id = ?",
                (drop_id,),
            )
            duplicate_drop_ids.append(drop_id)

    conn.commit()

    after = audit(cur)

    report = {
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "before": before,
        "deactivated_bad_choice_ids": deactivated_bad_choice_ids,
        "duplicate_keep_ids": duplicate_keep_ids,
        "duplicate_drop_ids": duplicate_drop_ids,
        "after": after,
    }

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
