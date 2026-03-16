from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"
LATEST_AUDIT = sorted(BASE.glob("artifacts/forbidden_lemma_audit_*/forbidden_lemma_reject.csv"))[-1]
TS = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
OUT_DIR = BASE / "artifacts" / f"forbidden_lemma_apply_{TS}"
BACKUP = OUT_DIR / f"lingua_staging_before_forbidden_lemma_apply_{TS}.db"

MANUAL_KEEP_IDS = {1481, 1955}

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, BACKUP)

    with LATEST_AUDIT.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    reject_ids = sorted({
        int(r["id"])
        for r in rows
        if str(r.get("id", "")).isdigit() and int(r["id"]) not in MANUAL_KEEP_IDS
    })

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    before_active = conn.execute(
        "SELECT COUNT(*) AS n FROM vocab_items WHERE is_active = 1"
    ).fetchone()["n"]

    applied_remove = 0
    already_inactive = 0
    missing_item = 0
    preview = []

    for item_id in reject_ids:
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
        preview.append({
            "id": row["id"],
            "lemma": row["lemma"],
            "correct_answer": row["correct_answer"],
            "pos": row["pos"],
            "bin_name": row["bin_name"],
        })

    conn.commit()

    after_active = conn.execute(
        "SELECT COUNT(*) AS n FROM vocab_items WHERE is_active = 1"
    ).fetchone()["n"]

    by_pos = conn.execute(
        """
        SELECT pos, COUNT(*) AS n
        FROM vocab_items
        WHERE is_active = 1
        GROUP BY pos
        ORDER BY n DESC
        """
    ).fetchall()

    by_bin = conn.execute(
        """
        SELECT bin_name, COUNT(*) AS n
        FROM vocab_items
        WHERE is_active = 1
        GROUP BY bin_name
        ORDER BY n DESC
        """
    ).fetchall()

    summary = {
        "source_reject_csv": str(LATEST_AUDIT),
        "output_dir": str(OUT_DIR),
        "db_backup": str(BACKUP),
        "manual_keep_ids": sorted(MANUAL_KEEP_IDS),
        "reject_ids": reject_ids,
        "applied_remove": applied_remove,
        "already_inactive": already_inactive,
        "missing_item": missing_item,
        "active_before": before_active,
        "active_after": after_active,
        "active_by_pos_after": {str(r["pos"]): int(r["n"]) for r in by_pos},
        "active_by_bin_after": {str(r["bin_name"]): int(r["n"]) for r in by_bin},
    }

    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (OUT_DIR / "remove_preview.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "lemma", "correct_answer", "pos", "bin_name"])
        writer.writeheader()
        writer.writerows(preview)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    conn.close()

if __name__ == "__main__":
    main()
