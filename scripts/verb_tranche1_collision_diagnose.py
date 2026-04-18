#!/usr/bin/env python3
"""
verb_tranche1_collision_diagnose.py

Read-only diagnostic: explain why all 33 READY verb items fail collision checks.
Counts which Rule fires for each item and shows the active bank size at check time.
"""
from __future__ import annotations

import json
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
AUDIT_JSON = "diagnostics_exports/verb_tranche1/current/verb_tranche1_gloss_audit.json"

conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

# Active bank stats
active_count = conn.execute("SELECT COUNT(*) FROM vocab_items WHERE is_active=1").fetchone()[0]
active_ca_count = conn.execute(
    "SELECT COUNT(DISTINCT correct_answer) FROM vocab_items WHERE is_active=1 AND correct_answer IS NOT NULL"
).fetchone()[0]
active_distractor_count = conn.execute(
    "SELECT COUNT(DISTINCT vc.choice_text) FROM vocab_choices vc "
    "JOIN vocab_items vi ON vi.id=vc.item_id WHERE vi.is_active=1 AND vc.is_correct=0"
).fetchone()[0]

print(f"Active bank: {active_count} items")
print(f"Distinct active correct_answers: {active_ca_count}")
print(f"Distinct active distractors: {active_distractor_count}")

# Build sets
active_cas = set(
    r[0].strip() for r in
    conn.execute("SELECT correct_answer FROM vocab_items WHERE is_active=1 AND correct_answer IS NOT NULL")
    .fetchall()
)
active_distractors_set = set(
    r[0].strip() for r in
    conn.execute(
        "SELECT DISTINCT vc.choice_text FROM vocab_choices vc "
        "JOIN vocab_items vi ON vi.id=vc.item_id WHERE vi.is_active=1 AND vc.is_correct=0"
    ).fetchall()
)

# Load READY items
with open(AUDIT_JSON) as f:
    all_audited = json.load(f)
ready_items = [r for r in all_audited if r["candidate_class"] == "READY"]

print(f"\nREADY items to check: {len(ready_items)}")
print()

fail_dup = 0
fail_r1a_only = 0
fail_r1b_only = 0
fail_both = 0
pass_count = 0

print("=== PER-ITEM COLLISION BREAKDOWN ===")
for item in ready_items:
    item_id = item["item_id"]
    lemma = item["lemma"]
    ca = (item["correct_answer"] or "").strip()
    bin_name = item["bin_name"]

    # Duplicate lemma
    dup_row = conn.execute(
        "SELECT id FROM vocab_items WHERE lemma=? AND is_active=1", (lemma,)
    ).fetchone()
    dup_fail = dup_row is not None

    # Get choices
    choices = conn.execute(
        "SELECT choice_text, is_correct FROM vocab_choices WHERE item_id=? AND is_correct=0",
        (item_id,)
    ).fetchall()
    distractors = [(r[0] or "").strip() for r in choices]

    # Rule 1a: ca in active_distractors
    r1a_fail = ca in active_distractors_set

    # Rule 1b: any distractor in active_cas
    r1b_hits = [d for d in distractors if d and d in active_cas]
    r1b_fail = len(r1b_hits) > 0

    if dup_fail:
        fail_dup += 1
        status = "FAIL(dup)"
    elif r1a_fail and r1b_fail:
        fail_both += 1
        status = "FAIL(R1a+R1b)"
    elif r1a_fail:
        fail_r1a_only += 1
        status = "FAIL(R1a)"
    elif r1b_fail:
        fail_r1b_only += 1
        status = "FAIL(R1b)"
    else:
        pass_count += 1
        status = "PASS"

    r1b_summary = f" R1b_hits={len(r1b_hits)}" if r1b_fail else ""
    print(f"  {status:<16} id={item_id:<6} bin={bin_name:<5} lemma={lemma:<22} ca={ca}{r1b_summary}")

print()
print("=== SUMMARY ===")
print(f"  PASS:          {pass_count}")
print(f"  FAIL(dup):     {fail_dup}")
print(f"  FAIL(R1a):     {fail_r1a_only}")
print(f"  FAIL(R1b):     {fail_r1b_only}")
print(f"  FAIL(R1a+R1b): {fail_both}")
print(f"  TOTAL:         {len(ready_items)}")

print()
print("=== ROOT CAUSE ANALYSIS ===")
print(f"  The active bank has {active_ca_count} distinct correct_answers (Russian words).")
print(f"  Inactive verb items have 5-6 distractors each, drawn from common Russian verbs.")
print(f"  With {active_ca_count} 'occupied' Russian words, Rule 1b fires on almost every item.")
print(f"  The inactive pool predates the current {active_count}-item active bank.")
print(f"  Distractors were valid when written but are now CAs of active items.")

print()
print("=== OPTION: Would removing verb-POS-only Rule 1b cross-POS collision help? ===")
# Check: would items pass if we only check Rule 1b against active verbs (same POS)?
active_verb_cas = set(
    r[0].strip() for r in
    conn.execute(
        "SELECT correct_answer FROM vocab_items WHERE is_active=1 AND pos='verb' AND correct_answer IS NOT NULL"
    ).fetchall()
)
print(f"  Active VERB correct_answers only: {len(active_verb_cas)}")
pass_verb_only = 0
for item in ready_items:
    item_id = item["item_id"]
    lemma = item["lemma"]
    ca = (item["correct_answer"] or "").strip()
    dup_row = conn.execute(
        "SELECT id FROM vocab_items WHERE lemma=? AND is_active=1", (lemma,)
    ).fetchone()
    if dup_row:
        continue
    choices = conn.execute(
        "SELECT choice_text FROM vocab_choices WHERE item_id=? AND is_correct=0", (item_id,)
    ).fetchall()
    distractors = [(r[0] or "").strip() for r in choices]
    r1b_hits = [d for d in distractors if d and d in active_verb_cas]
    r1a_fail = ca in active_distractors_set
    if not r1a_fail and not r1b_hits:
        pass_verb_only += 1
print(f"  Items that would pass with verb-only Rule 1b: {pass_verb_only}")
print(f"  NOTE: Cross-POS Rule 1b is the design — items choosing correct POS-specific CA as distractor")
print(f"  would create measurement ambiguity (learner sees a word that IS a correct answer elsewhere).")

conn.close()
