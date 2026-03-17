from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data" / "lingua_staging.db"
OUT = ROOT / "artifacts" / "vocab_progression_reader_v1_20260317"
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
MIN_GROUP_SUPPORT = 2
MIN_POS_SUPPORT = 2
MIN_CEFR_SUPPORT = 2

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
required = {"vocab_attempts", "vocab_answers", "vocab_items"}
missing = sorted(required - tables)
if missing:
    raise SystemExit(f"Missing required tables: {missing}")

item_cols = {row[1] for row in cur.execute("PRAGMA table_info(vocab_items)")}
activity_col = "is_active" if "is_active" in item_cols else ("active" if "active" in item_cols else None)
if activity_col is None:
    raise SystemExit("No activity column on vocab_items")

attempt_cols = {row[1] for row in cur.execute("PRAGMA table_info(vocab_attempts)")}
answer_cols = {row[1] for row in cur.execute("PRAGMA table_info(vocab_answers)")}

answer_attempt_fk = "attempt_id" if "attempt_id" in answer_cols else None
answer_item_fk = "item_id" if "item_id" in answer_cols else None

is_correct_col = None
for cand in ("is_correct", "correct", "was_correct"):
    if cand in answer_cols:
        is_correct_col = cand
        break
if is_correct_col is None:
    raise SystemExit("No correctness column on vocab_answers")

latest_attempt = cur.execute("""
    SELECT id, result_snapshot_json
    FROM vocab_attempts
    WHERE result_snapshot_json IS NOT NULL
      AND TRIM(result_snapshot_json) != ''
    ORDER BY id DESC
    LIMIT 1
""").fetchone()

if latest_attempt is None:
    payload = {
        "status": "no_finished_attempts",
        "message": "No vocab attempt with result_snapshot_json found."
    }
    (OUT / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0)

attempt_id = latest_attempt["id"]
snapshot = json.loads(latest_attempt["result_snapshot_json"])

rows = cur.execute(f"""
    SELECT
        va.{answer_item_fk} AS item_id,
        va.{is_correct_col} AS is_correct,
        vi.lemma,
        vi.pos,
        vi.cefr_estimate,
        vi.concept_group,
        vi.freq_rank,
        vi.correct_answer
    FROM vocab_answers va
    JOIN vocab_items vi ON vi.id = va.{answer_item_fk}
    WHERE va.{answer_attempt_fk} = ?
    ORDER BY va.rowid
""", (attempt_id,)).fetchall()

bank_rows = cur.execute(f"""
    SELECT pos, cefr_estimate, concept_group
    FROM vocab_items
    WHERE {activity_col} = 1
""").fetchall()

def truthy(v) -> int:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return 1 if v != 0 else 0
    s = str(v).strip().lower()
    return 1 if s in {"1", "true", "t", "yes"} else 0

answered_total = len(rows)
correct_total = sum(truthy(r["is_correct"]) for r in rows)
ratio = round(correct_total / answered_total, 4) if answered_total else None

by_pos = defaultdict(lambda: {"correct": 0, "total": 0})
by_cefr = defaultdict(lambda: {"correct": 0, "total": 0})
by_group = defaultdict(lambda: {"correct": 0, "total": 0})

bank_pos = defaultdict(int)
bank_cefr = defaultdict(int)
bank_group = defaultdict(int)

known_lemmas = []
weak_lemmas = []

for r in rows:
    ok = truthy(r["is_correct"])
    pos = (r["pos"] or "other").strip()
    cefr = (r["cefr_estimate"] or "unknown").strip()
    cg = (r["concept_group"] or "").strip()
    lemma = (r["lemma"] or "").strip()

    by_pos[pos]["correct"] += ok
    by_pos[pos]["total"] += 1
    by_cefr[cefr]["correct"] += ok
    by_cefr[cefr]["total"] += 1

    if cg in MEANINGFUL_GROUPS:
        by_group[cg]["correct"] += ok
        by_group[cg]["total"] += 1

    item = {
        "lemma": lemma,
        "pos": pos,
        "cefr_estimate": cefr,
        "concept_group": cg if cg in MEANINGFUL_GROUPS else None,
        "freq_rank": r["freq_rank"],
        "correct_answer": r["correct_answer"],
        "is_correct": ok,
    }
    if ok:
        known_lemmas.append(item)
    else:
        weak_lemmas.append(item)

for r in bank_rows:
    pos = (r["pos"] or "other").strip()
    cefr = (r["cefr_estimate"] or "unknown").strip()
    cg = (r["concept_group"] or "").strip()
    bank_pos[pos] += 1
    bank_cefr[cefr] += 1
    if cg in MEANINGFUL_GROUPS:
        bank_group[cg] += 1

def bucket_stats(d: dict[str, dict[str, int]], min_support: int):
    rows = []
    for k, v in d.items():
        total = v["total"]
        if total < min_support:
            continue
        correct = v["correct"]
        acc = round(correct / total, 4) if total else 0.0
        rows.append({
            "key": k,
            "correct": correct,
            "total": total,
            "accuracy": acc,
        })
    return rows

def sorted_desc(rows):
    return sorted(rows, key=lambda x: (-x["accuracy"], -x["total"], x["key"]))

def sorted_asc(rows):
    return sorted(rows, key=lambda x: (x["accuracy"], -x["total"], x["key"]))

pos_rows = bucket_stats(by_pos, MIN_POS_SUPPORT)
cefr_rows = bucket_stats(by_cefr, MIN_CEFR_SUPPORT)
group_rows = bucket_stats(by_group, MIN_GROUP_SUPPORT)

observed_pos_keys = sorted(by_pos.keys())
single_pos_attempt = len(observed_pos_keys) <= 1

strongest_pos = [] if single_pos_attempt else sorted_desc(pos_rows)[:5]
weakest_pos = [] if single_pos_attempt else sorted_asc(pos_rows)[:5]

strongest_cefr = sorted_desc(cefr_rows)[:6]
weakest_cefr = sorted_asc(cefr_rows)[:6]
strongest_groups = sorted_desc(group_rows)[:10]
weakest_groups = sorted_asc(group_rows)[:10]

profile = {
    "attempt_id": attempt_id,
    "lexical_baseline": {
        "estimated_vocab_size_band": snapshot.get("product_band"),
        "confidence": snapshot.get("confidence"),
        "correctness_ratio": ratio,
        "correct_count": correct_total,
        "total_questions": answered_total,
    },
    "observed_attempt_profile": {
        "pos_counts": dict(sorted((k, v["total"]) for k, v in by_pos.items())),
        "cefr_counts": dict(sorted((k, v["total"]) for k, v in by_cefr.items())),
        "meaningful_concept_group_counts": dict(sorted((k, v["total"]) for k, v in by_group.items())),
    },
    "bank_baseline_profile": {
        "active_pos_counts": dict(sorted(bank_pos.items())),
        "active_cefr_counts": dict(sorted(bank_cefr.items())),
        "active_meaningful_concept_group_counts": dict(sorted(bank_group.items())),
    },
    "lexical_profile": {
        "strongest_pos": strongest_pos,
        "weakest_pos": weakest_pos,
        "strongest_cefr": strongest_cefr,
        "weakest_cefr": weakest_cefr,
        "strongest_concept_groups": strongest_groups,
        "weak_concept_groups": weakest_groups,
        "known_lemmas_sample": known_lemmas[:15],
        "weak_lemmas_sample": weak_lemmas[:15],
    },
    "progression_ready_hints": {
        "recommended_lesson_packs": [x["key"] for x in weakest_groups[:3]],
        "recommended_game_packs": [x["key"] for x in weakest_pos[:2]],
        "ready_for_level_focus": bool(snapshot.get("correct_count", 0) >= 8),
        "ready_for_ciple_focus": bool(snapshot.get("correct_count", 0) >= 12),
    },
    "signal_quality": {
        "single_pos_attempt": single_pos_attempt,
        "meaningful_concept_group_support_total": sum(v["total"] for v in by_group.values()),
        "recommended_lesson_packs_confident": len(weakest_groups) > 0,
        "recommended_game_packs_confident": len(weakest_pos) > 0,
    },
    "notes": [
        "Reader v2 hardening: weakest/strongest signals are suppressed when support is too low.",
        "Concept-group recommendations require meaningful groups and minimum support.",
        "Bank baseline profile is included to separate attempt composition from inventory composition."
    ],
}

summary = {
    "db": str(DB),
    "attempt_id": attempt_id,
    "answered_total": answered_total,
    "correct_total": correct_total,
    "profile": profile,
}

(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(summary, ensure_ascii=False, indent=2))
conn.close()
