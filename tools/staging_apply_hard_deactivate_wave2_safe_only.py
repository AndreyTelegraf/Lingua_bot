from __future__ import annotations
import csv
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
SRC_DIR = ROOT / "data/master_source_v1/processed/staging_build_hard_deactivate_candidates_wave2"
SRC_CSV = SRC_DIR / "hard_deactivate_candidates_wave2.csv"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_apply_hard_deactivate_wave2_safe_only"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SAFE_REASONS = {"functionish_surface", "awkward_ru_gloss", "proper_name_like"}

if not SRC_CSV.exists():
    raise SystemExit(f"Missing source csv: {SRC_CSV}")

backup_path = OUT_DIR / f"lingua_staging.before_apply_hard_deactivate_wave2_safe_only.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.db"
shutil.copy2(DB, backup_path)

targets: list[dict] = []
with SRC_CSV.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        reasons = {x.strip() for x in (row.get("reasons") or "").split("|") if x.strip()}
        if reasons & SAFE_REASONS:
            row["matched_safe_reasons"] = "|".join(sorted(reasons & SAFE_REASONS))
            targets.append(row)

target_ids = [int(r["item_id"]) for r in targets]
target_ids = sorted(set(target_ids))

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

item_cols = [r["name"] for r in cur.execute("PRAGMA table_info(vocab_items)")]
active_col = "is_active" if "is_active" in item_cols else "active"

before_rows = []
if target_ids:
    placeholders = ",".join("?" for _ in target_ids)
    before_rows = [dict(r) for r in cur.execute(
        f"""
        SELECT id AS item_id, lemma, correct_answer, pos, topic_tag, bin_name, freq_rank, {active_col} AS active_value
        FROM vocab_items
        WHERE id IN ({placeholders})
        ORDER BY id
        """,
        target_ids,
    ).fetchall()]

if target_ids:
    cur.execute(
        f"UPDATE vocab_items SET {active_col}=0 WHERE id IN ({','.join('?' for _ in target_ids)})",
        target_ids,
    )
    conn.commit()

after_rows = []
if target_ids:
    placeholders = ",".join("?" for _ in target_ids)
    after_rows = [dict(r) for r in cur.execute(
        f"""
        SELECT id AS item_id, lemma, correct_answer, pos, {active_col} AS active_value
        FROM vocab_items
        WHERE id IN ({placeholders})
        ORDER BY id
        """,
        target_ids,
    ).fetchall()]

active_total_after = cur.execute(f"SELECT COUNT(*) AS c FROM vocab_items WHERE {active_col}=1").fetchone()["c"]

csv_out = OUT_DIR / "deactivated_items.csv"
with csv_out.open("w", encoding="utf-8", newline="") as f:
    fieldnames = [
        "item_id", "lemma", "correct_answer", "pos", "topic_tag", "bin_name",
        "freq_rank", "reasons", "matched_safe_reasons", "choices_preview"
    ]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in targets:
        writer.writerow({k: row.get(k, "") for k in fieldnames})

summary = {
    "db": str(DB),
    "source_csv": str(SRC_CSV),
    "backup": str(backup_path),
    "safe_reasons": sorted(SAFE_REASONS),
    "targets_count": len(target_ids),
    "target_ids": target_ids,
    "before": before_rows,
    "after": after_rows,
    "active_total_after": active_total_after,
    "utc_timestamp": datetime.now(timezone.utc).isoformat(),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(summary, ensure_ascii=False, indent=2))
conn.close()
