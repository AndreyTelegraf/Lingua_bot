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
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, UTC

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"
CSV = BASE / "tools" / "safe_batch50_gate_v1_3_marked.csv"

TS = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
OUT_DIR = BASE / "artifacts" / f"safe_batch50_apply_{TS}"
BACKUP = OUT_DIR / f"lingua_staging_before_safe_batch50_apply_{TS}.db"

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, BACKUP)

    rows = list(csv.DictReader(CSV.open(encoding="utf-8", newline="")))

    keep_ids: list[int] = []
    reject_ids: list[int] = []
    review_ids: list[int] = []

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    for r in rows:
        status = (r.get("manual_gate_status") or "").strip().upper()
        item_id = int(r["id"])
        if status == "KEEP":
            keep_ids.append(item_id)
        elif status.startswith("REJECT"):
            reject_ids.append(item_id)
        else:
            review_ids.append(item_id)

    if keep_ids:
        conn.execute(
            f"UPDATE vocab_items SET is_active = 1 WHERE id IN ({','.join(map(str, keep_ids))})"
        )
    if reject_ids:
        conn.execute(
            f"UPDATE vocab_items SET is_active = 0 WHERE id IN ({','.join(map(str, reject_ids))})"
        )

    conn.commit()

    active_total = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE is_active = 1"
    ).fetchone()[0]

    summary = {
        "source_csv": str(CSV),
        "output_dir": str(OUT_DIR),
        "db_backup": str(BACKUP),
        "keep_count": len(keep_ids),
        "reject_count": len(reject_ids),
        "review_count": len(review_ids),
        "keep_ids": keep_ids,
        "reject_ids": reject_ids,
        "review_ids": review_ids,
        "active_total": active_total,
    }

    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    print("\n===== KEPT ITEMS =====")
    if keep_ids:
        for row in conn.execute(
            f"SELECT id, lemma, freq_rank FROM vocab_items WHERE id IN ({','.join(map(str, keep_ids))}) ORDER BY freq_rank, id"
        ):
            print(f"{row['id']}|{row['lemma']}|{row['freq_rank']}")

    print("\n===== REJECTED ITEMS =====")
    if reject_ids:
        for row in conn.execute(
            f"SELECT id, lemma, freq_rank FROM vocab_items WHERE id IN ({','.join(map(str, reject_ids))}) ORDER BY freq_rank, id"
        ):
            print(f"{row['id']}|{row['lemma']}|{row['freq_rank']}")

    conn.close()

if __name__ == "__main__":
    main()
