from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data" / "lingua_staging.db"
OUT = ROOT / "artifacts" / "vocab_progression_profile_contract_20260317"
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

tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}

item_cols = {row[1] for row in cur.execute("PRAGMA table_info(vocab_items)")}
activity_col = "is_active" if "is_active" in item_cols else ("active" if "active" in item_cols else None)
if activity_col is None:
    raise SystemExit("No activity column found on vocab_items")

# latest finished attempt snapshot if available
baseline = {
    "estimated_vocab_size_band": None,
    "confidence": None,
    "correctness_ratio": None,
    "correct_count": None,
    "total_questions": None,
}

if "vocab_attempts" in tables:
    attempt_cols = {row[1] for row in cur.execute("PRAGMA table_info(vocab_attempts)")}
    if "result_snapshot_json" in attempt_cols:
        row = cur.execute("""
            SELECT result_snapshot_json
            FROM vocab_attempts
            WHERE result_snapshot_json IS NOT NULL
              AND TRIM(result_snapshot_json) != ''
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()
        if row:
            try:
                snap = json.loads(row["result_snapshot_json"])
                baseline["estimated_vocab_size_band"] = snap.get("product_band")
                baseline["confidence"] = snap.get("confidence")
                baseline["correct_count"] = snap.get("correct_count")
                baseline["total_questions"] = snap.get("total_questions")
                cc = snap.get("correct_count")
                tq = snap.get("total_questions")
                if isinstance(cc, int) and isinstance(tq, int) and tq > 0:
                    baseline["correctness_ratio"] = round(cc / tq, 4)
            except Exception:
                pass

rows = cur.execute(
    f"""
    SELECT id, lemma, pos, cefr_estimate, concept_group, freq_rank
    FROM vocab_items
    WHERE {activity_col} = 1
    """
).fetchall()

pos_counter = Counter()
cefr_counter = Counter()
group_counter = Counter()
lemma_samples = defaultdict(list)

for r in rows:
    pos = r["pos"] or "other"
    cefr = r["cefr_estimate"] or "unknown"
    cg = r["concept_group"] or None
    lemma = r["lemma"] or None
    freq_rank = r["freq_rank"]

    pos_counter[pos] += 1
    cefr_counter[cefr] += 1
    if cg in MEANINGFUL_GROUPS:
        group_counter[cg] += 1
    if lemma and len(lemma_samples[pos]) < 20:
        lemma_samples[pos].append({"lemma": lemma, "freq_rank": freq_rank})

def topn(counter: Counter, n: int = 5):
    return [{"key": k, "count": v} for k, v in counter.most_common(n)]

# This is a contract scaffold, not user scoring yet.
# Weaknesses are placeholders until per-user item/event aggregation is wired.
profile = {
    "lexical_baseline": baseline,
    "lexical_profile": {
        "strongest_pos": topn(pos_counter, 4),
        "weakest_pos": list(reversed(sorted(
            [{"key": k, "count": v} for k, v in pos_counter.items()],
            key=lambda x: (x["count"], x["key"])
        )))[:0],  # intentionally empty until user-level aggregation
        "strongest_cefr": topn(cefr_counter, 6),
        "weakest_cefr": [],
        "strongest_concept_groups": topn(group_counter, 10),
        "weak_concept_groups": [],
        "known_lemmas_sample": {
            k: v[:10] for k, v in lemma_samples.items()
        },
        "weak_lemmas_sample": [],
    },
    "progression_ready_hints": {
        "recommended_lesson_packs": [],
        "recommended_game_packs": [],
        "ready_for_level_focus": None,
        "ready_for_ciple_focus": None,
    },
    "contract_notes": [
        "Structured JSON contract for progression graph reader.",
        "User-level weak areas remain empty until attempt/item join layer is implemented.",
        "Only meaningful concept groups are surfaced here; fallback concept_group=lemma is intentionally excluded from top group signals.",
    ],
}

summary = {
    "db": str(DB),
    "tables_seen": sorted(tables),
    "active_item_total": len(rows),
    "contract_json": profile,
}

summary_path = OUT / "summary.json"
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
contract_path = OUT / "contract.json"
contract_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(summary, ensure_ascii=False, indent=2))
conn.close()
