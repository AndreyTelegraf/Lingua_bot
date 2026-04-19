"""
Stage 1 — Target Set Reconfirmation for adverb 5K activation pack.
Read-only. No DB writes.
"""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/lingua_staging.db")
OUT_DIR = Path("diagnostics_exports/adverb_5k_activation/current")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_IDS = [3958, 3960, 10017, 3963, 10019, 3970]

# Correct answers from live validation
EXPECTED = {
    3958:  {"lemma": "frequentemente",  "correct_answer": "часто"},
    3960:  {"lemma": "geralmente",      "correct_answer": "обычно"},
    10017: {"lemma": "novamente",       "correct_answer": "снова"},
    3963:  {"lemma": "principalmente",  "correct_answer": "главным образом"},
    10019: {"lemma": "exatamente",      "correct_answer": "точно"},
    3970:  {"lemma": "facilmente",      "correct_answer": "легко"},
}

con = sqlite3.connect(DB_PATH)
con.row_factory = sqlite3.Row
cur = con.cursor()

results = []
blockers = []

for iid in TARGET_IDS:
    cur.execute("""
        SELECT id, lemma, pos, bin_name, correct_answer, is_active
        FROM vocab_items
        WHERE id = ?
    """, (iid,))
    row = cur.fetchone()
    r = {"item_id": iid}

    if row is None:
        r["exists"] = False
        blockers.append(f"item_id={iid}: NOT FOUND in DB")
        results.append(r)
        continue

    r["exists"] = True
    r["lemma"] = row["lemma"]
    r["pos"] = row["pos"]
    r["bin_name"] = row["bin_name"]
    r["correct_answer"] = row["correct_answer"]
    r["is_active"] = row["is_active"]

    # Choices
    cur.execute("""
        SELECT choice_text, is_correct FROM vocab_choices WHERE item_id = ? ORDER BY is_correct DESC
    """, (iid,))
    choices = [dict(c) for c in cur.fetchall()]
    r["choices"] = choices
    n_choices = len(choices)
    n_correct = sum(1 for c in choices if c["is_correct"])
    n_distractor = n_choices - n_correct

    # Checks
    checks = {}
    checks["pos_adverb"] = row["pos"] == "adverb"
    checks["bin_5k"] = row["bin_name"] == "5K"
    checks["is_inactive"] = row["is_active"] == 0
    checks["lemma_match"] = row["lemma"] == EXPECTED[iid]["lemma"]
    checks["correct_answer_match"] = row["correct_answer"].strip() == EXPECTED[iid]["correct_answer"]
    checks["exactly_4_choices"] = n_choices == 4
    checks["exactly_1_correct"] = n_correct == 1
    checks["exactly_3_distractors"] = n_distractor == 3

    # Rule 1a: correct_answer not among distractors of other group items
    other_distractors = set()
    for other_id in TARGET_IDS:
        if other_id == iid:
            continue
        cur.execute("""
            SELECT choice_text FROM vocab_choices WHERE item_id = ? AND is_correct = 0
        """, (other_id,))
        for c in cur.fetchall():
            other_distractors.add(c["choice_text"])
    rule_1a_pass = row["correct_answer"] not in other_distractors
    checks["rule_1a_correct_answer_not_in_others_distractors"] = rule_1a_pass

    # Rule 1b: this item's distractors not equal to any other item's correct_answer
    my_distractors = {c["choice_text"] for c in choices if c["is_correct"] == 0}
    other_cas = {EXPECTED[oid]["correct_answer"] for oid in TARGET_IDS if oid != iid}
    rule_1b_collisions = my_distractors & other_cas
    checks["rule_1b_distractors_not_correct_answers_of_others"] = len(rule_1b_collisions) == 0
    if rule_1b_collisions:
        r["rule_1b_collisions"] = list(rule_1b_collisions)

    # Choice integrity: no empty, no dupes within item
    choice_texts = [c["choice_text"] for c in choices]
    checks["no_empty_choices"] = all(t and t.strip() for t in choice_texts)
    checks["no_duplicate_choices"] = len(set(choice_texts)) == n_choices

    item_pass = all(checks.values())
    r["checks"] = checks
    r["item_pass"] = item_pass

    if not item_pass:
        for k, v in checks.items():
            if not v:
                blockers.append(f"item_id={iid} ({row['lemma']}): FAIL {k}")

    results.append(r)

# Group atomic consistency: no CA appears as distractor in same group
group_cas = {EXPECTED[iid]["correct_answer"] for iid in TARGET_IDS}
group_atomic_issues = []
for iid in TARGET_IDS:
    cur.execute("SELECT choice_text FROM vocab_choices WHERE item_id = ? AND is_correct = 0", (iid,))
    distractors = {c["choice_text"] for c in cur.fetchall()}
    collisions = distractors & group_cas
    if collisions:
        group_atomic_issues.append({"item_id": iid, "collisions": list(collisions)})

# Duplicate lemma check vs active bank (same lemma active elsewhere)
dup_lemma_issues = []
for iid in TARGET_IDS:
    lemma = EXPECTED[iid]["lemma"]
    cur.execute("""
        SELECT id FROM vocab_items WHERE lemma = ? AND is_active = 1 AND id != ?
    """, (lemma, iid))
    actives = cur.fetchall()
    if actives:
        dup_lemma_issues.append({"item_id": iid, "lemma": lemma, "active_duplicates": [r["id"] for r in actives]})

con.close()

group_atomic_pass = len(group_atomic_issues) == 0
duplicate_lemma_pass = len(dup_lemma_issues) == 0
all_items_pass = all(r.get("item_pass", False) for r in results)
stage1_pass = all_items_pass and group_atomic_pass and duplicate_lemma_pass

# --- Markdown report ---
lines = ["# Adverb 5K Activation — Stage 1: Target Set Reconfirmation", ""]
lines.append(f"**Stage 1 verdict: {'PASS' if stage1_pass else 'FAIL'}**")
lines.append("")
lines.append("## Item-level results")
lines.append("")
lines.append("| item_id | lemma | pos | bin_name | correct_answer | is_active | item_pass |")
lines.append("|---------|-------|-----|----------|----------------|-----------|-----------|")
for r in results:
    if not r.get("exists", True):
        lines.append(f"| {r['item_id']} | — | — | — | — | — | **NOT FOUND** |")
    else:
        lines.append(
            f"| {r['item_id']} | {r['lemma']} | {r['pos']} | {r['bin_name']} "
            f"| {r['correct_answer']} | {r['is_active']} | {'✓' if r['item_pass'] else '✗'} |"
        )

lines.append("")
lines.append("## Group-level checks")
lines.append("")
lines.append(f"- Group atomic consistency: {'PASS' if group_atomic_pass else 'FAIL'}")
if group_atomic_issues:
    for iss in group_atomic_issues:
        lines.append(f"  - item_id={iss['item_id']}: CA collision in distractors: {iss['collisions']}")
lines.append(f"- Duplicate lemma vs active bank: {'PASS' if duplicate_lemma_pass else 'FAIL'}")
if dup_lemma_issues:
    for iss in dup_lemma_issues:
        lines.append(f"  - item_id={iss['item_id']} ({iss['lemma']}): active duplicates: {iss['active_duplicates']}")

if blockers:
    lines.append("")
    lines.append("## Blockers")
    for b in blockers:
        lines.append(f"- {b}")

lines.append("")
lines.append("## Choices per item")
for r in results:
    if not r.get("exists", True):
        continue
    lines.append(f"### {r['item_id']} — {r['lemma']}")
    for c in r["choices"]:
        marker = "✓" if c["is_correct"] else "✗"
        lines.append(f"  {marker} {c['choice_text']}")
    lines.append("")

lines.append("---")
lines.append(f"**Acceptance: {'PASS — safe to build activation pack' if stage1_pass else 'FAIL — blockers must be resolved'}**")

out_md = OUT_DIR / "adverb_5k_target_reconfirmation.md"
out_md.write_text("\n".join(lines))

# Print summary
print("=" * 60)
print("STAGE 1 — TARGET SET RECONFIRMATION")
print("=" * 60)
for r in results:
    if r.get("exists", True):
        status = "PASS" if r.get("item_pass") else "FAIL"
        print(f"  [{status}] item_id={r['item_id']} lemma={r['lemma']} bin={r['bin_name']} ca={r['correct_answer']} is_active={r['is_active']}")
    else:
        print(f"  [FAIL] item_id={r['item_id']} NOT FOUND")

print(f"\nGroup atomic consistency: {'PASS' if group_atomic_pass else 'FAIL'}")
print(f"Duplicate lemma check:    {'PASS' if duplicate_lemma_pass else 'FAIL'}")
print(f"\nStage 1 overall: {'PASS' if stage1_pass else 'FAIL'}")
if blockers:
    print("\nBLOCKERS:")
    for b in blockers:
        print(f"  - {b}")

print(f"\nOutput: {out_md}")
print(f"\nStage 1 exit: {'GO' if stage1_pass else 'STOP'}")
