from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data/lingua_staging.db"
TS = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
OUT_DIR = BASE / "artifacts" / f"policy_apply_v3_{TS}"
BACKUP = OUT_DIR / f"lingua_staging_before_policy_apply_v3_{TS}.db"
CSV_PATH = BASE / "tools" / "active_bank_manual_audit_heuristic_marked.csv"

KEEP_ACTIVE_IDS = {95, 542, 163, 566}
FORCE_REMOVE_IDS = {3348, 681}
REBUILD_KEEP_IDS = {163, 566}

REMOVE_FLAGS = {
    "LIKELY_COGNATE",
    "BAD_CHOICE_SHAPE",
}

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, BACKUP)

    with CSV_PATH.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    remove_candidates = []
    rebuild_keep_rows = []

    for r in rows:
        try:
            item_id = int(r["id"])
        except Exception:
            continue

        flags = {
            x.strip()
            for x in (r.get("heuristic_flags") or "").split(";")
            if x.strip()
        }

        if item_id in REBUILD_KEEP_IDS:
            rebuild_keep_rows.append(
                {
                    "id": item_id,
                    "lemma": r.get("lemma", ""),
                    "correct_answer": r.get("correct_answer", ""),
                    "heuristic_flags": r.get("heuristic_flags", ""),
                    "triage_status": r.get("triage_status", ""),
                    "action": "KEEP_SEMANTICS_REBUILD_CHOICES",
                }
            )

        should_remove = False
        reason_bits = []

        if item_id in FORCE_REMOVE_IDS:
            should_remove = True
            reason_bits.append("FORCE_REMOVE_ID")

        matched_remove_flags = sorted(flags & REMOVE_FLAGS)
        if matched_remove_flags:
            should_remove = True
            reason_bits.extend(matched_remove_flags)

        if should_remove and item_id not in KEEP_ACTIVE_IDS:
            remove_candidates.append(
                {
                    "id": item_id,
                    "lemma": r.get("lemma", ""),
                    "correct_answer": r.get("correct_answer", ""),
                    "heuristic_flags": r.get("heuristic_flags", ""),
                    "triage_status": r.get("triage_status", ""),
                    "remove_reason": ";".join(reason_bits),
                }
            )

    remove_ids = sorted({int(r["id"]) for r in remove_candidates})

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    before_active = conn.execute(
        "SELECT COUNT(*) AS n FROM vocab_items WHERE is_active = 1"
    ).fetchone()["n"]

    applied_remove = 0
    already_inactive = 0
    missing_item = 0
    remove_preview = []

    for item_id in remove_ids:
        row = conn.execute(
            "SELECT id, lemma, correct_answer, pos, bin_name, is_active FROM vocab_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if row is None:
            missing_item += 1
            continue
        if int(row["is_active"] or 0) != 1:
            already_inactive += 1
            continue

        conn.execute(
            "UPDATE vocab_items SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (item_id,),
        )
        applied_remove += 1
        remove_preview.append(
            {
                "id": row["id"],
                "lemma": row["lemma"],
                "correct_answer": row["correct_answer"],
                "pos": row["pos"],
                "bin_name": row["bin_name"],
            }
        )

    conn.commit()

    after_active = conn.execute(
        "SELECT COUNT(*) AS n FROM vocab_items WHERE is_active = 1"
    ).fetchone()["n"]

    ready_pos = conn.execute(
        """
        WITH ready_items AS (
            SELECT vc.item_id
            FROM vocab_choices vc
            GROUP BY vc.item_id
            HAVING COUNT(*) = 6
        )
        SELECT vi.pos AS pos, COUNT(*) AS n
        FROM vocab_items vi
        JOIN ready_items ri ON ri.item_id = vi.id
        WHERE vi.is_active = 1
        GROUP BY vi.pos
        ORDER BY n DESC
        """
    ).fetchall()

    ready_bin = conn.execute(
        """
        WITH ready_items AS (
            SELECT vc.item_id
            FROM vocab_choices vc
            GROUP BY vc.item_id
            HAVING COUNT(*) = 6
        )
        SELECT vi.bin_name AS bin_name, COUNT(*) AS n
        FROM vocab_items vi
        JOIN ready_items ri ON ri.item_id = vi.id
        WHERE vi.is_active = 1
        GROUP BY vi.bin_name
        ORDER BY n DESC
        """
    ).fetchall()

    summary = {
        "source_csv": str(CSV_PATH),
        "output_dir": str(OUT_DIR),
        "db_backup": str(BACKUP),
        "csv_rows": len(rows),
        "policy_remove_flags": sorted(REMOVE_FLAGS),
        "keep_active_ids": sorted(KEEP_ACTIVE_IDS),
        "force_remove_ids": sorted(FORCE_REMOVE_IDS),
        "rebuild_keep_ids": sorted(REBUILD_KEEP_IDS),
        "remove_candidate_count": len(remove_candidates),
        "remove_ids": remove_ids,
        "applied_remove": applied_remove,
        "already_inactive": already_inactive,
        "missing_item": missing_item,
        "active_before": before_active,
        "active_after": after_active,
        "ready_items_by_pos_after": {
            ("NULL" if r["pos"] is None else str(r["pos"])): int(r["n"]) for r in ready_pos
        },
        "ready_items_by_bin_after": {
            ("NULL" if r["bin_name"] is None else str(r["bin_name"])): int(r["n"]) for r in ready_bin
        },
    }

    (OUT_DIR / "apply_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (OUT_DIR / "remove_preview.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["id", "lemma", "correct_answer", "pos", "bin_name"],
        )
        writer.writeheader()
        writer.writerows(remove_preview)

    with (OUT_DIR / "rebuild_keep_ids.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["id", "lemma", "correct_answer", "heuristic_flags", "triage_status", "action"],
        )
        writer.writeheader()
        writer.writerows(rebuild_keep_rows)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    conn.close()

if __name__ == "__main__":
    main()
