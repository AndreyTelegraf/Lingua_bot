from __future__ import annotations

import json
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime, UTC
from pathlib import Path

DB_PATH = Path("data/lingua_staging.db")
TMP_DIR = Path("tmp")
BACKUP_DIR = TMP_DIR / "db_backups"
REPORT_PATH = TMP_DIR / "fix_20k_adjectives_active_inactive_duplicates_report.json"


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def main() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    backup_path = BACKUP_DIR / f"lingua_staging_before_fix_20k_adjectives_active_inactive_duplicates_{utc_stamp()}.db"
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
            COALESCE(SUM(CASE WHEN COALESCE(vc.is_correct, 0) = 1 THEN 1 ELSE 0 END), 0) AS correct_count
        FROM vocab_items vi
        LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.pos = 'adjective'
          AND vi.bin_name = '20K'
        GROUP BY
            vi.id, vi.lemma, vi.correct_answer, vi.pos, vi.bin_name,
            vi.freq_rank, vi.is_active, vi.topic_tag
        ORDER BY vi.lemma, vi.is_active DESC, vi.freq_rank, vi.id
        """
    ).fetchall()

    buckets: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for r in rows:
        buckets[r["lemma"]].append(r)

    delete_ids: list[int] = []
    applied_groups: list[dict] = []
    skipped_groups: list[dict] = []

    for lemma, grp in sorted(buckets.items()):
        if len(grp) <= 1:
            continue

        active_rows = [r for r in grp if int(r["is_active"]) == 1]
        inactive_rows = [r for r in grp if int(r["is_active"]) == 0]

        if len(active_rows) != 1 or len(inactive_rows) == 0:
            skipped_groups.append({
                "lemma": lemma,
                "reason": "not_exactly_one_active",
                "row_ids": [int(r["id"]) for r in grp],
            })
            continue

        active = active_rows[0]

        safe_inactive = []
        unsafe_inactive = []

        for r in inactive_rows:
            same_answer = (r["correct_answer"] == active["correct_answer"])
            usable = int(r["choice_count"]) > 0
            structurally_ok = int(r["choice_count"]) == 6 and int(r["correct_count"]) == 1

            if same_answer and usable and structurally_ok:
                safe_inactive.append(r)
            else:
                unsafe_inactive.append({
                    "id": int(r["id"]),
                    "correct_answer": r["correct_answer"],
                    "choice_count": int(r["choice_count"]),
                    "correct_count": int(r["correct_count"]),
                    "topic_tag": r["topic_tag"],
                })

        if unsafe_inactive:
            skipped_groups.append({
                "lemma": lemma,
                "reason": "inactive_rows_not_safe",
                "active_id": int(active["id"]),
                "unsafe_inactive": unsafe_inactive,
            })
            continue

        if not safe_inactive:
            skipped_groups.append({
                "lemma": lemma,
                "reason": "no_safe_inactive_rows",
                "active_id": int(active["id"]),
            })
            continue

        ids = [int(r["id"]) for r in safe_inactive]
        delete_ids.extend(ids)
        applied_groups.append({
            "lemma": lemma,
            "active_id": int(active["id"]),
            "active_correct_answer": active["correct_answer"],
            "deleted_inactive_ids": ids,
        })

    if delete_ids:
        conn.executemany("DELETE FROM vocab_choices WHERE item_id = ?", [(x,) for x in delete_ids])
        conn.executemany("DELETE FROM vocab_items WHERE id = ?", [(x,) for x in delete_ids])
        conn.commit()

    remaining_dups = conn.execute(
        """
        WITH layer AS (
            SELECT lemma
            FROM vocab_items
            WHERE pos = 'adjective' AND bin_name = '20K'
        )
        SELECT COUNT(*)
        FROM (
            SELECT lemma
            FROM layer
            GROUP BY lemma
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]

    report = {
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "deleted_item_count": len(delete_ids),
        "deleted_ids": delete_ids,
        "applied_group_count": len(applied_groups),
        "remaining_duplicate_group_count": int(remaining_dups),
        "applied_groups": applied_groups,
        "skipped_groups": skipped_groups,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("===== FIX 20K ADJECTIVES ACTIVE/INACTIVE DUPLICATES =====")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
