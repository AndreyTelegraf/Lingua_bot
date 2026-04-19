"""
Stage 2 — Activation Pack Generation for adverb 5K.
Generates manifest, collision report, and summary.
Read-only. No DB writes. No activation.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("data/lingua_staging.db")
OUT_DIR = Path("diagnostics_exports/adverb_5k_activation/current")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_IDS = [3958, 3960, 10017, 3963, 10019, 3970]

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

manifest_items = []
collision_items = []
all_pass = True

group_cas = {EXPECTED[iid]["correct_answer"] for iid in TARGET_IDS}

for iid in TARGET_IDS:
    cur.execute("""
        SELECT id, lemma, pos, bin_name, correct_answer, is_active
        FROM vocab_items WHERE id = ?
    """, (iid,))
    row = cur.fetchone()

    cur.execute("""
        SELECT choice_text, is_correct FROM vocab_choices WHERE item_id = ? ORDER BY is_correct DESC
    """, (iid,))
    choices = [dict(c) for c in cur.fetchall()]
    n_choices = len(choices)
    n_correct = sum(1 for c in choices if c["is_correct"])
    choice_texts = [c["choice_text"] for c in choices]
    my_distractors = {c["choice_text"] for c in choices if c["is_correct"] == 0}
    other_cas = {EXPECTED[oid]["correct_answer"] for oid in TARGET_IDS if oid != iid}

    # Rule 1a: my CA not in others' distractors
    rule_1a_violations = []
    my_ca = row["correct_answer"]
    for oid in TARGET_IDS:
        if oid == iid:
            continue
        cur.execute("SELECT choice_text FROM vocab_choices WHERE item_id = ? AND is_correct = 0", (oid,))
        od = {c["choice_text"] for c in cur.fetchall()}
        if my_ca in od:
            rule_1a_violations.append(oid)
    rule_1a_pass = len(rule_1a_violations) == 0

    # Rule 1b: my distractors not equal to other CAs
    rule_1b_collisions = list(my_distractors & other_cas)
    rule_1b_pass = len(rule_1b_collisions) == 0

    # Group atomic: none of group CAs appear as my distractors
    group_atomic_pass = len(my_distractors & group_cas) == 0

    # Duplicate lemma vs active bank
    cur.execute("SELECT id FROM vocab_items WHERE lemma = ? AND is_active = 1 AND id != ?", (row["lemma"], iid))
    dup_actives = [r["id"] for r in cur.fetchall()]
    dup_lemma_pass = len(dup_actives) == 0

    # Choice integrity
    choice_integrity_pass = (
        n_choices == 4 and
        n_correct == 1 and
        all(t and t.strip() for t in choice_texts) and
        len(set(choice_texts)) == n_choices
    )

    item_all_pass = rule_1a_pass and rule_1b_pass and group_atomic_pass and dup_lemma_pass and choice_integrity_pass
    if not item_all_pass:
        all_pass = False

    manifest_items.append({
        "item_id": iid,
        "lemma": row["lemma"],
        "bin_name": row["bin_name"],
        "pos": row["pos"],
        "correct_answer": row["correct_answer"],
        "is_active": row["is_active"],
        "choices": choices,
        "validation_status": "PASS" if item_all_pass else "FAIL",
        "readiness_status": "ACTIVATION_READY_PREPARED" if item_all_pass else "NOT_READY",
    })

    collision_items.append({
        "item_id": iid,
        "lemma": row["lemma"],
        "rule_1a_pass": rule_1a_pass,
        "rule_1a_detail": f"violations_in_items: {rule_1a_violations}" if rule_1a_violations else "clean",
        "rule_1b_pass": rule_1b_pass,
        "rule_1b_detail": f"collisions: {rule_1b_collisions}" if rule_1b_collisions else "clean",
        "group_atomic_consistency_pass": group_atomic_pass,
        "duplicate_lemma_pass": dup_lemma_pass,
        "duplicate_active_ids": dup_actives,
        "choice_integrity_pass": choice_integrity_pass,
        "item_all_pass": item_all_pass,
    })

con.close()

# --- Manifest JSON ---
manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "stage": "PREPARE_ONLY",
    "activation_status": "NOT_ACTIVATED",
    "total_items": len(manifest_items),
    "all_ready": all_pass,
    "items": manifest_items,
}
manifest_path = OUT_DIR / "adverb_5k_activation_manifest.json"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

# --- Collision Report JSON ---
collision_report = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "stage": "PREPARE_ONLY",
    "total_items": len(collision_items),
    "all_pass": all_pass,
    "items": collision_items,
}
collision_path = OUT_DIR / "adverb_5k_activation_collision_report.json"
collision_path.write_text(json.dumps(collision_report, ensure_ascii=False, indent=2))

# --- Summary MD ---
lines = ["# Adverb 5K Activation — Stage 2: Activation Pack", ""]
lines.append(f"Generated: {manifest['generated_at']}")
lines.append(f"**Stage: PREPARE_ONLY — No activation performed**")
lines.append("")
lines.append("## Manifest")
lines.append("")
lines.append("| item_id | lemma | bin | correct_answer | is_active | readiness_status |")
lines.append("|---------|-------|-----|----------------|-----------|-----------------|")
for item in manifest_items:
    lines.append(
        f"| {item['item_id']} | {item['lemma']} | {item['bin_name']} "
        f"| {item['correct_answer']} | {item['is_active']} | {item['readiness_status']} |"
    )

lines.append("")
lines.append("## Collision Report Summary")
lines.append("")
lines.append("| item_id | lemma | Rule 1a | Rule 1b | Group Atomic | Dup Lemma | Choice Integrity | ALL |")
lines.append("|---------|-------|---------|---------|-------------|-----------|-----------------|-----|")
for item in collision_items:
    def yn(v):
        return "✓" if v else "✗"
    lines.append(
        f"| {item['item_id']} | {item['lemma']} | {yn(item['rule_1a_pass'])} "
        f"| {yn(item['rule_1b_pass'])} | {yn(item['group_atomic_consistency_pass'])} "
        f"| {yn(item['duplicate_lemma_pass'])} | {yn(item['choice_integrity_pass'])} "
        f"| {yn(item['item_all_pass'])} |"
    )

lines.append("")
lines.append(f"**Overall: {'ALL PASS — ACTIVATION_READY_PREPARED' if all_pass else 'FAIL — see collision report'}**")
lines.append("")
lines.append("---")
lines.append("Files generated:")
lines.append(f"- {manifest_path}")
lines.append(f"- {collision_path}")

summary_path = OUT_DIR / "adverb_5k_activation_summary.md"
summary_path.write_text("\n".join(lines))

print("=" * 60)
print("STAGE 2 — ACTIVATION PACK GENERATION")
print("=" * 60)
print(f"\nManifest:          {manifest_path}")
print(f"Collision report:  {collision_path}")
print(f"Summary:           {summary_path}")
print(f"\nTotal items: {len(manifest_items)}")
print(f"All ready:   {all_pass}")
for item in manifest_items:
    print(f"  [{item['readiness_status']}] id={item['item_id']} lemma={item['lemma']}")

print(f"\nStage 2 exit: {'GO' if all_pass else 'STOP'}")
