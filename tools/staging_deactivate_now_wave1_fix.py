from __future__ import annotations
import json
import shutil
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_deactivate_now_wave1_fix"
OUT_DIR.mkdir(parents=True, exist_ok=True)

targets = [
    {"pk": 973, "lemma": "armamento", "expected_correct_answer": "вооружения", "reason": "correct_not_in_choices"},
    {"pk": 2027, "lemma": "músculo", "expected_correct_answer": "мышцы", "reason": "correct_not_in_choices"},
    {"pk": 3479, "lemma": "bangladesh", "expected_correct_answer": None, "reason": "proper_name_like"},
]

if not DB.exists():
    raise SystemExit(f"DB not found: {DB}")

backup = OUT_DIR / f"lingua_staging.before_deactivate_now_wave1_fix.{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.db"
shutil.copy2(DB, backup)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

table_info = cur.execute("PRAGMA table_info(vocab_items)").fetchall()
cols = [dict(r) for r in table_info]
col_names = [r["name"] for r in table_info]

pk_col = None
for r in table_info:
    if int(r["pk"]) == 1:
        pk_col = r["name"]
        break
if pk_col is None:
    for cand in ("id", "item_id"):
        if cand in col_names:
            pk_col = cand
            break
if pk_col is None:
    raise SystemExit(f"Could not detect PK column in vocab_items. Columns: {col_names}")

active_col = next((c for c in ("is_active", "active") if c in col_names), None)
if active_col is None:
    raise SystemExit(f"Could not detect active column. Columns: {col_names}")

lemma_col = "lemma" if "lemma" in col_names else None
correct_col = next((c for c in ("correct_answer", "answer_ru", "translation_ru") if c in col_names), None)
choices_col = next((c for c in ("choices_json", "choices", "option_texts_json") if c in col_names), None)
updated_at_col = "updated_at" if "updated_at" in col_names else None

before = []
for t in targets:
    row = cur.execute(f"SELECT * FROM vocab_items WHERE {pk_col} = ?", (t["pk"],)).fetchone()
    if row is None:
        raise SystemExit(f"Target not found: {pk_col}={t['pk']}")
    d = dict(row)
    before.append({
        "pk": t["pk"],
        "lemma": d.get(lemma_col) if lemma_col else None,
        "correct_answer": d.get(correct_col) if correct_col else None,
        "active_before": d.get(active_col),
        "choices": d.get(choices_col) if choices_col else None,
        "reason": t["reason"],
    })
    if lemma_col and d.get(lemma_col) != t["lemma"]:
        raise SystemExit(
            f"Lemma mismatch for {pk_col}={t['pk']}: expected {t['lemma']!r}, got {d.get(lemma_col)!r}"
        )
    if correct_col and t["expected_correct_answer"] is not None and d.get(correct_col) != t["expected_correct_answer"]:
        raise SystemExit(
            f"Correct-answer mismatch for {pk_col}={t['pk']}: expected {t['expected_correct_answer']!r}, got {d.get(correct_col)!r}"
        )

for t in targets:
    if updated_at_col:
        cur.execute(
            f"UPDATE vocab_items SET {active_col} = 0, {updated_at_col} = CURRENT_TIMESTAMP WHERE {pk_col} = ?",
            (t["pk"],),
        )
    else:
        cur.execute(
            f"UPDATE vocab_items SET {active_col} = 0 WHERE {pk_col} = ?",
            (t["pk"],),
        )

conn.commit()

after = []
for t in targets:
    row = cur.execute(
        f"SELECT {pk_col} AS pk, {active_col} AS active_value"
        + (f", {lemma_col} AS lemma" if lemma_col else "")
        + (f", {correct_col} AS correct_answer" if correct_col else "")
        + f" FROM vocab_items WHERE {pk_col} = ?",
        (t["pk"],),
    ).fetchone()
    after.append(dict(row))

active_total = cur.execute(f"SELECT COUNT(*) AS c FROM vocab_items WHERE {active_col} = 1").fetchone()["c"]

summary = {
    "db": str(DB),
    "backup": str(backup),
    "pk_col": pk_col,
    "active_col": active_col,
    "lemma_col": lemma_col,
    "correct_col": correct_col,
    "choices_col": choices_col,
    "columns": col_names,
    "before": before,
    "after": after,
    "active_total_after": active_total,
    "utc_timestamp": datetime.now(UTC).isoformat(),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))

conn.close()
