from __future__ import annotations
import csv
import json
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
IN_DIR = ROOT / "data/master_source_v1/processed/staging_high_review_workbench_wave1"
IN_REPAIR = IN_DIR / "high_review_repair_first.csv"
IN_SEM = IN_DIR / "high_review_semantic_review.csv"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_deactivate_high_embarrassment_wave1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not DB.exists():
    raise SystemExit(f"DB not found: {DB}")
if not IN_REPAIR.exists():
    raise SystemExit(f"Missing input CSV: {IN_REPAIR}")
if not IN_SEM.exists():
    raise SystemExit(f"Missing input CSV: {IN_SEM}")

def load_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

repair_rows = load_rows(IN_REPAIR)
sem_rows = load_rows(IN_SEM)
targets_src = repair_rows + sem_rows

targets = []
seen = set()
for r in targets_src:
    item_pk = int(r["item_pk"])
    if item_pk in seen:
        continue
    seen.add(item_pk)
    targets.append({
        "item_pk": item_pk,
        "lemma": r["lemma"],
        "correct_answer": r["correct_answer"],
        "source_family": r["source_family"],
        "auto_bucket": r["auto_bucket"],
        "suggested_action": r["suggested_action"],
        "reason_codes": r["reason_codes"],
        "choices_preview": r["choices_preview"],
    })

if not targets:
    raise SystemExit("No targets loaded from repair/semantic CSVs")

backup = OUT_DIR / f"lingua_staging.before_deactivate_high_embarrassment_wave1.{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.db"
shutil.copy2(DB, backup)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cols = [dict(r) for r in cur.execute("PRAGMA table_info(vocab_items)").fetchall()]
col_names = [r["name"] for r in cols]
pk_col = next((r["name"] for r in cols if int(r["pk"]) == 1), None) or ("id" if "id" in col_names else "item_id")
active_col = "is_active" if "is_active" in col_names else "active"
updated_at_col = "updated_at" if "updated_at" in col_names else None

before = []
for t in targets:
    row = cur.execute(
        f"SELECT {pk_col} AS item_pk, lemma, correct_answer, pos, topic_tag, bin_name, freq_rank, {active_col} AS active_value FROM vocab_items WHERE {pk_col} = ?",
        (t["item_pk"],),
    ).fetchone()
    if row is None:
        raise SystemExit(f"Missing target in DB: {t['item_pk']}")
    row = dict(row)
    if row["lemma"] != t["lemma"]:
        raise SystemExit(f"Lemma mismatch for {t['item_pk']}: csv={t['lemma']!r} db={row['lemma']!r}")
    before.append({
        **row,
        "source_family": t["source_family"],
        "auto_bucket": t["auto_bucket"],
        "suggested_action": t["suggested_action"],
        "reason_codes": t["reason_codes"],
        "choices_preview": t["choices_preview"],
    })

for t in targets:
    if updated_at_col:
        cur.execute(
            f"UPDATE vocab_items SET {active_col} = 0, {updated_at_col} = CURRENT_TIMESTAMP WHERE {pk_col} = ?",
            (t["item_pk"],),
        )
    else:
        cur.execute(
            f"UPDATE vocab_items SET {active_col} = 0 WHERE {pk_col} = ?",
            (t["item_pk"],),
        )

conn.commit()

after = []
for t in targets:
    row = cur.execute(
        f"SELECT {pk_col} AS item_pk, lemma, correct_answer, pos, {active_col} AS active_value FROM vocab_items WHERE {pk_col} = ?",
        (t["item_pk"],),
    ).fetchone()
    after.append(dict(row))

bad = [r for r in after if int(r["active_value"]) != 0]
if bad:
    raise SystemExit(f"Deactivate assert failed: {bad}")

active_total = cur.execute(f"SELECT COUNT(*) AS c FROM vocab_items WHERE {active_col}=1").fetchone()["c"]

summary = {
    "db": str(DB),
    "backup": str(backup),
    "pk_col": pk_col,
    "active_col": active_col,
    "targets_count": len(targets),
    "source_family_counts": dict(Counter(t["source_family"] for t in targets).most_common()),
    "reason_code_counts": dict(Counter(
        code
        for t in targets
        for code in (t["reason_codes"].split("|") if t["reason_codes"] else [])
        if code
    ).most_common()),
    "item_pks": [t["item_pk"] for t in targets],
    "before": before,
    "after": after,
    "active_total_after": active_total,
    "utc_timestamp": datetime.now(UTC).isoformat(),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

with (OUT_DIR / "deactivated_items.csv").open("w", encoding="utf-8", newline="") as f:
    cols = [
        "item_pk", "lemma", "correct_answer", "pos", "topic_tag", "bin_name", "freq_rank",
        "source_family", "auto_bucket", "suggested_action", "reason_codes", "choices_preview"
    ]
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in before:
        w.writerow({k: r.get(k) for k in cols})

print(json.dumps(summary, ensure_ascii=False, indent=2))
conn.close()
