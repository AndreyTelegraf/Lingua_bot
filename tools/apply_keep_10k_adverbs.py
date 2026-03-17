from __future__ import annotations

import os
import sys

if os.environ.get("LINGUABOT_ALLOW_UNSAFE_DIRECT_ACTIVATION") != "1":
    raise SystemExit(
        "Blocked: this legacy script performs direct vocab_items.is_active=1 writes and bypasses the strict activation gate in services/vocab_bank/validate_items.py. "
        "Use the canonical publish path instead. "
        "Override only for forensic/manual recovery with LINGUABOT_ALLOW_UNSAFE_DIRECT_ACTIVATION=1."
    )

import csv, json, sqlite3
from pathlib import Path
from datetime import datetime, UTC

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"
CSV = BASE / "tools" / "targeted_expansion_probe_10k_adverbs_v2_marked.csv"
OUT_DIR = BASE / "artifacts" / f"apply_keep_10k_adverbs_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

OUT_DIR.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

backup = OUT_DIR / "lingua_staging_backup.db"
with open(DB, "rb") as src, open(backup, "wb") as dst:
    dst.write(src.read())

keep_ids = []
with open(CSV, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if (r.get("manual_status") or "").strip() == "KEEP":
            keep_ids.append(int(r["id"]))

activated = []
for i in keep_ids:
    conn.execute("UPDATE vocab_items SET is_active = 1 WHERE id = ?", (i,))
    activated.append(i)

conn.commit()

active_total = conn.execute(
    "SELECT COUNT(*) FROM vocab_items WHERE is_active = 1"
).fetchone()[0]

active_10k_adverbs = conn.execute("""
    SELECT COUNT(*)
    FROM vocab_items
    WHERE is_active = 1 AND bin_name = '10K' AND pos = 'adverb'
""").fetchone()[0]

summary = {
    "activated_count": len(activated),
    "activated_ids": activated,
    "active_total_after": active_total,
    "active_10k_adverbs_after": active_10k_adverbs,
    "backup": str(backup),
    "csv_source": str(CSV),
}

print(json.dumps(summary, ensure_ascii=False, indent=2))
conn.close()
