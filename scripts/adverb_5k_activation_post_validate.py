"""
Stage 3 — Live post-activation validation for adverb 5K.
Read-only. Validates all 6 items are now active and all rules still hold.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("data/lingua_staging.db")
OUT_DIR = Path("diagnostics_exports/adverb_5k_activation/current")

TARGET_IDS = [3958, 3960, 10017, 3963, 10019, 3970]
EXPECTED = {
    3958:  {"lemma": "frequentemente",  "correct_answer": "часто"},
    3960:  {"lemma": "geralmente",      "correct_answer": "обычно"},
    10017: {"lemma": "novamente",       "correct_answer": "снова"},
    3963:  {"lemma": "principalmente",  "correct_answer": "главным образом"},
    10019: {"lemma": "exatamente",      "correct_answer": "точно"},
    3970:  {"lemma": "facilmente",      "correct_answer": "легко"},
}
BASELINE = {"adverb": 40, "noun": 397, "verb": 185}
EXPECTED_AFTER = {"adverb": 46, "noun": 397, "verb": 185}

con = sqlite3.connect(DB_PATH)
con.row_factory = sqlite3.Row
cur = con.cursor()

results = []
blockers = []

group_cas = {EXPECTED[iid]["correct_answer"] for iid in TARGET_IDS}

for iid in TARGET_IDS:
    cur.execute("SELECT id, lemma, pos, bin_name, correct_answer, is_active FROM vocab_items WHERE id = ?", (iid,))
    row = cur.fetchone()
    r = {"item_id": iid}

    if row is None:
        r["exists"] = False
        blockers.append(f"item_id={iid}: NOT FOUND")
        results.append(r)
        continue

    r["exists"] = True
    r["lemma"] = row["lemma"]
    r["pos"] = row["pos"]
    r["bin_name"] = row["bin_name"]
    r["correct_answer"] = row["correct_answer"]
    r["is_active"] = row["is_active"]

    cur.execute("SELECT choice_text, is_correct FROM vocab_choices WHERE item_id = ? ORDER BY is_correct DESC", (iid,))
    choices = [dict(c) for c in cur.fetchall()]
    choice_texts = [c["choice_text"] for c in choices]
    my_distractors = {c["choice_text"] for c in choices if c["is_correct"] == 0}
    other_cas = {EXPECTED[oid]["correct_answer"] for oid in TARGET_IDS if oid != iid}
    n_choices = len(choices)
    n_correct = sum(1 for c in choices if c["is_correct"])

    checks = {}
    checks["is_active_1"] = row["is_active"] == 1
    checks["pos_adverb"] = row["pos"] == "adverb"
    checks["bin_5k"] = row["bin_name"] == "5K"
    checks["lemma_match"] = row["lemma"] == EXPECTED[iid]["lemma"]
    checks["correct_answer_match"] = row["correct_answer"] == EXPECTED[iid]["correct_answer"]
    checks["exactly_4_choices"] = n_choices == 4
    checks["exactly_1_correct"] = n_correct == 1
    checks["no_empty_choices"] = all(t and t.strip() for t in choice_texts)
    checks["no_duplicate_choices"] = len(set(choice_texts)) == n_choices

    # Rule 1a
    rule_1a_pass = True
    for oid in TARGET_IDS:
        if oid == iid:
            continue
        cur.execute("SELECT COUNT(*) as cnt FROM vocab_choices WHERE item_id=? AND is_correct=0 AND choice_text=?",
                    (oid, row["correct_answer"]))
        if cur.fetchone()["cnt"] > 0:
            rule_1a_pass = False
            blockers.append(f"item_id={iid}: Rule 1a fail — CA '{row['correct_answer']}' in distractors of {oid}")
    checks["rule_1a"] = rule_1a_pass

    # Rule 1b
    rule_1b_collisions = list(my_distractors & other_cas)
    checks["rule_1b"] = len(rule_1b_collisions) == 0
    if rule_1b_collisions:
        blockers.append(f"item_id={iid}: Rule 1b fail — collisions {rule_1b_collisions}")

    # Group atomic
    group_atomic_collisions = list(my_distractors & group_cas)
    checks["group_atomic_consistency"] = len(group_atomic_collisions) == 0
    if group_atomic_collisions:
        blockers.append(f"item_id={iid}: Group atomic fail — {group_atomic_collisions}")

    # Duplicate lemma vs active (exclude self since now active)
    cur.execute("SELECT id FROM vocab_items WHERE lemma=? AND is_active=1 AND id!=?", (row["lemma"], iid))
    dup_actives = [r2["id"] for r2 in cur.fetchall()]
    checks["duplicate_lemma_pass"] = len(dup_actives) == 0
    if dup_actives:
        blockers.append(f"item_id={iid}: Duplicate active lemma: {dup_actives}")

    item_pass = all(checks.values())
    if not item_pass:
        for k, v in checks.items():
            if not v:
                blockers.append(f"item_id={iid} ({row['lemma']}): FAIL {k}")
    r["checks"] = checks
    r["choices"] = choices
    r["item_pass"] = item_pass
    results.append(r)

# POS count drift check
drift_checks = {}
for pos in ("adverb", "noun", "verb"):
    cur.execute("SELECT COUNT(*) as cnt FROM vocab_items WHERE is_active=1 AND pos=?", (pos,))
    actual = cur.fetchone()["cnt"]
    expected = EXPECTED_AFTER[pos]
    drift_checks[pos] = {"actual": actual, "expected": expected, "pass": actual == expected}

cur.execute("SELECT COUNT(*) as cnt FROM vocab_items WHERE is_active=1 AND pos='adverb' AND bin_name='5K'")
adverb_5k_count = cur.fetchone()["cnt"]

con.close()

all_items_pass = all(r.get("item_pass", False) for r in results)
drift_pass = all(v["pass"] for v in drift_checks.values())
stage3_pass = all_items_pass and drift_pass

# --- JSON output ---
json_out = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "stage3_pass": stage3_pass,
    "all_items_pass": all_items_pass,
    "drift_pass": drift_pass,
    "adverb_5k_active_count": adverb_5k_count,
    "pos_counts": drift_checks,
    "results": results,
}
json_path = OUT_DIR / "adverb_5k_post_activation_validation.json"
json_path.write_text(json.dumps(json_out, ensure_ascii=False, indent=2))

# --- Markdown output ---
lines = ["# Adverb 5K Activation — Stage 3: Post-Activation Validation", ""]
lines.append(f"Generated: {json_out['generated_at']}")
lines.append(f"**Stage 3 verdict: {'PASS' if stage3_pass else 'FAIL'}**")
lines.append("")
lines.append("## Item Validation")
lines.append("")
lines.append("| item_id | lemma | is_active | Rule 1a | Rule 1b | Group Atomic | Dup Lemma | Choice OK | ALL |")
lines.append("|---------|-------|-----------|---------|---------|-------------|-----------|-----------|-----|")
for r in results:
    if not r.get("exists", True):
        lines.append(f"| {r['item_id']} | — | — | — | — | — | — | — | NOT FOUND |")
        continue
    def yn(v): return "✓" if v else "✗"
    c = r["checks"]
    lines.append(
        f"| {r['item_id']} | {r['lemma']} | {r['is_active']} "
        f"| {yn(c['rule_1a'])} | {yn(c['rule_1b'])} | {yn(c['group_atomic_consistency'])} "
        f"| {yn(c['duplicate_lemma_pass'])} | {yn(c['exactly_4_choices'] and c['exactly_1_correct'])} "
        f"| {yn(r['item_pass'])} |"
    )

lines.append("")
lines.append("## POS Count Drift Check")
lines.append("")
lines.append("| POS | Baseline | Expected | Actual | Pass |")
lines.append("|-----|---------|---------|--------|------|")
for pos, v in drift_checks.items():
    lines.append(f"| {pos} | {BASELINE[pos]} | {v['expected']} | {v['actual']} | {'✓' if v['pass'] else '✗'} |")
lines.append(f"| adverb/5K | — | — | {adverb_5k_count} | — |")

if blockers:
    lines.append("")
    lines.append("## Blockers")
    for b in blockers:
        lines.append(f"- {b}")

lines.append("")
lines.append(f"**Stage 3 Acceptance: {'PASS' if stage3_pass else 'FAIL'}**")

md_path = OUT_DIR / "adverb_5k_post_activation_validation.md"
md_path.write_text("\n".join(lines))

print("=" * 60)
print("STAGE 3 — POST-ACTIVATION VALIDATION")
print("=" * 60)
for r in results:
    status = "PASS" if r.get("item_pass") else "FAIL"
    active = r.get("is_active", "?")
    print(f"  [{status}] id={r['item_id']} lemma={r.get('lemma','?')} is_active={active}")

print("\nPOS drift check:")
for pos, v in drift_checks.items():
    marker = "OK" if v["pass"] else "FAIL"
    print(f"  [{marker}] {pos}: expected={v['expected']} actual={v['actual']}")
print(f"  Active adverb/5K: {adverb_5k_count}")

if blockers:
    print("\nBLOCKERS:")
    for b in blockers:
        print(f"  - {b}")

print(f"\nStage 3 overall: {'PASS' if stage3_pass else 'FAIL'}")
print(f"\nOutput JSON: {json_path}")
print(f"Output MD:   {md_path}")
