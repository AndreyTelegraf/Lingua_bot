from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

DB_PATH = Path("data/lingua_staging.db")
TMP_DIR = Path("tmp")
BACKUP_DIR = TMP_DIR / "db_backups"
REPORT_PATH = TMP_DIR / "fix_20k_nouns_active_inactive_duplicates_report.json"


def now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    backup_path = BACKUP_DIR / f"lingua_staging_before_fix_20k_nouns_active_inactive_duplicates_{now_stamp()}.db"
    shutil.copy2(DB_PATH, backup_path)

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
          COALESCE(COUNT(vc.id), 0) AS choice_count,
          COALESCE(SUM(CASE WHEN COALESCE(vc.is_correct,0)=1 THEN 1 ELSE 0 END), 0) AS correct_count
        FROM vocab_items vi
        LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.pos = 'noun' AND vi.bin_name = '20K'
        GROUP BY
          vi.id, vi.lemma, vi.correct_answer, vi.pos, vi.bin_name,
          vi.freq_rank, vi.is_active, vi.topic_tag
        ORDER BY vi.freq_rank, vi.id
        """
    ).fetchall()

    buckets: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        buckets.setdefault(str(r["lemma"]), []).append(r)

    applied_groups: list[dict] = []
    skipped_groups: list[dict] = []
    delete_ids: list[int] = []

    for lemma, grp in sorted(buckets.items()):
        if len(grp) <= 1:
            continue

        active_rows = [r for r in grp if int(r["is_active"]) == 1]
        inactive_rows = [r for r in grp if int(r["is_active"]) == 0]

        if len(active_rows) != 1 or len(inactive_rows) < 1:
            skipped_groups.append({
                "lemma": lemma,
                "reason": "not_exactly_one_active_plus_inactive",
                "row_ids": [int(r["id"]) for r in grp],
            })
            continue

        active = active_rows[0]

        compatible = True
        bad_rows: list[int] = []

        for r in inactive_rows:
            if str(r["correct_answer"]) != str(active["correct_answer"]):
                compatible = False
                bad_rows.append(int(r["id"]))
                continue
            if int(r["choice_count"]) != 6 or int(r["correct_count"]) != 1:
                compatible = False
                bad_rows.append(int(r["id"]))
                continue

        if not compatible:
            skipped_groups.append({
                "lemma": lemma,
                "reason": "inactive_rows_not_compatible_with_active",
                "active_id": int(active["id"]),
                "bad_rows": bad_rows,
            })
            continue

        inactive_ids = [int(r["id"]) for r in inactive_rows]
        delete_ids.extend(inactive_ids)
        applied_groups.append({
            "lemma": lemma,
            "active_id": int(active["id"]),
            "active_correct_answer": str(active["correct_answer"]),
            "deleted_inactive_ids": inactive_ids,
        })

    if delete_ids:
        conn.executemany(
            "DELETE FROM vocab_choices WHERE item_id = ?",
            [(item_id,) for item_id in delete_ids],
        )
        conn.executemany(
            "DELETE FROM vocab_items WHERE id = ?",
            [(item_id,) for item_id in delete_ids],
        )
        conn.commit()

    remaining = conn.execute(
        """
        WITH layer AS (
          SELECT id, lemma, is_active
          FROM vocab_items
          WHERE pos = 'noun' AND bin_name = '20K'
        ),
        dups AS (
          SELECT lemma
          FROM layer
          GROUP BY lemma
          HAVING COUNT(*) > 1
        )
        SELECT COUNT(*) AS cnt
        FROM dups
        """
    ).fetchone()

    report = {
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "deleted_item_count": len(delete_ids),
        "deleted_ids": delete_ids,
        "applied_group_count": len(applied_groups),
        "remaining_duplicate_group_count": int(remaining["cnt"]),
        "applied_groups": applied_groups,
        "skipped_groups": skipped_groups,
    }

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("===== FIX 20K NOUNS ACTIVE/INACTIVE DUPLICATES =====")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
