from __future__ import annotations

import os
import sys

if os.environ.get("LINGUABOT_ALLOW_UNSAFE_DIRECT_ACTIVATION") != "1":
    raise SystemExit(
        "Blocked: this legacy script performs direct vocab_items.is_active=1 writes and bypasses the strict activation gate in services/vocab_bank/validate_items.py. "
        "Use the canonical publish path instead. "
        "Override only for forensic/manual recovery with LINGUABOT_ALLOW_UNSAFE_DIRECT_ACTIVATION=1."
    )


import csv
import json
import shutil
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"
CSV_PATH = BASE / "tools" / "expansion_top200_promotable_gate_v1_2_marked_20260316.csv"

TS = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
OUT_DIR = BASE / "artifacts" / f"expansion_gate_v1_2_apply_{TS}"
BACKUP = OUT_DIR / f"lingua_staging_before_expansion_gate_v1_2_apply_{TS}.db"

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, BACKUP)

    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8", newline="")))

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    keep = []
    reject = []
    review = []

    for r in rows:
        item_id = int(r["id"])
        status = (r.get("manual_gate_status") or "").strip()

        if status == "KEEP":
            conn.execute(
                "UPDATE vocab_items SET is_active = 1 WHERE id = ?",
                (item_id,),
            )
            keep.append(item_id)

        elif status == "REJECT_TRANSPARENT":
            conn.execute(
                "UPDATE vocab_items SET is_active = 0 WHERE id = ?",
                (item_id,),
            )
            reject.append(item_id)

        elif status == "REVIEW":
            review.append(item_id)

    conn.commit()

    sanity = {
        "active_items": conn.execute(
            "SELECT COUNT(*) FROM vocab_items WHERE is_active = 1"
        ).fetchone()[0],
        "inactive_items": conn.execute(
            "SELECT COUNT(*) FROM vocab_items WHERE is_active = 0"
        ).fetchone()[0],
    }

    summary = {
        "source_csv": str(CSV_PATH),
        "output_dir": str(OUT_DIR),
        "db_backup": str(BACKUP),
        "keep_count": len(keep),
        "reject_count": len(reject),
        "review_count": len(review),
        "keep_ids": keep,
        "reject_ids": reject,
        "review_ids": review,
        "sanity": sanity,
    }

    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    conn.close()

if __name__ == "__main__":
    main()
