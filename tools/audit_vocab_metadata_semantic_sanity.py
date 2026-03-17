from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data" / "lingua_staging.db"
OUT = ROOT / "artifacts" / "vocab_metadata_semantic_sanity_20260317"
OUT.mkdir(parents=True, exist_ok=True)

MEANINGFUL_GROUPS = {
    "motion_basic",
    "core_verbs",
    "house_home",
    "food_daily",
    "work_employment",
    "health_body",
    "time_basic",
    "shopping_money",
    "transport_mobility",
    "greetings_social",
    "bureaucracy_documents",
}

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

item_cols = {row[1] for row in cur.execute("PRAGMA table_info(vocab_items)")}
activity_col = "is_active" if "is_active" in item_cols else ("active" if "active" in item_cols else None)
if activity_col is None:
    raise SystemExit("No activity column found on vocab_items")

rows = cur.execute(
    f"""
    SELECT id, lemma, pos, cefr_estimate, concept_group, freq_rank, correct_answer
    FROM vocab_items
    WHERE {activity_col} = 1
    ORDER BY id
    """
).fetchall()

active_total = len(rows)

def nonempty(v: object) -> bool:
    return v is not None and str(v).strip() != ""

meaningful = []
fallback_like = []
same_as_lemma = []
suspicious = []
top_counter = Counter()

for r in rows:
    lemma = (r["lemma"] or "").strip()
    cg = (r["concept_group"] or "").strip()
    ru = (r["correct_answer"] or "").strip()

    if nonempty(cg):
        top_counter[cg] += 1

    if nonempty(cg) and cg in MEANINGFUL_GROUPS:
        meaningful.append(dict(r))
    elif nonempty(cg) and lemma and cg == lemma:
        same_as_lemma.append(dict(r))
        fallback_like.append(dict(r))
    elif nonempty(cg):
        fallback_like.append(dict(r))
        if " " in cg or len(cg) <= 2:
            suspicious.append(dict(r))

summary = {
    "db": str(DB),
    "activity_col": activity_col,
    "active_total": active_total,
    "meaningful_concept_group_total": len(meaningful),
    "meaningful_concept_group_pct": round(len(meaningful) * 100.0 / active_total, 2) if active_total else 0.0,
    "fallback_like_concept_group_total": len(fallback_like),
    "fallback_like_concept_group_pct": round(len(fallback_like) * 100.0 / active_total, 2) if active_total else 0.0,
    "concept_group_equals_lemma_total": len(same_as_lemma),
    "concept_group_equals_lemma_pct": round(len(same_as_lemma) * 100.0 / active_total, 2) if active_total else 0.0,
    "suspicious_concept_group_total": len(suspicious),
    "top_meaningful_groups": [
        {"concept_group": k, "cnt": v}
        for k, v in top_counter.most_common(100)
        if k in MEANINGFUL_GROUPS
    ],
    "top_fallback_groups": [
        {"concept_group": k, "cnt": v}
        for k, v in top_counter.most_common(100)
        if k not in MEANINGFUL_GROUPS
    ][:50],
    "sample_meaningful": meaningful[:100],
    "sample_fallback_like": fallback_like[:100],
    "sample_suspicious": suspicious[:100],
}

summary_path = OUT / "summary.json"
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
conn.close()
