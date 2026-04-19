#!/usr/bin/env python3
"""
verb_tranche1_preactivation_audit.py
Stage 1 — Pre-activation safety audit. Read-only.
Outputs: diagnostics_exports/verb_tranche1/current/verb_tranche1_preactivation_audit.md
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
MANIFEST_PATH = "diagnostics_exports/verb_tranche1/current/verb_tranche1_activation_manifest.json"
ACTIVATE_SCRIPT = "scripts/verb_tranche1_activate_DONOTRUN.sh"
OUTPUT_DIR = "diagnostics_exports/verb_tranche1/current"

TARGET_IDS = [868, 921, 1732, 1759, 2172, 3467, 3491, 3509, 9328]


def main() -> int:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    manifest_ids = sorted(m["item_id"] for m in manifest["items"])

    with open(ACTIVATE_SCRIPT) as f:
        script_text = f.read()

    # Active bank sets
    active_cas: set[str] = set()
    for row in conn.execute(
        "SELECT correct_answer FROM vocab_items WHERE is_active=1 AND correct_answer IS NOT NULL"
    ).fetchall():
        ca = (row["correct_answer"] or "").strip()
        if ca:
            active_cas.add(ca)

    active_distractors: set[str] = set()
    for row in conn.execute(
        "SELECT DISTINCT vc.choice_text FROM vocab_choices vc "
        "JOIN vocab_items vi ON vi.id=vc.item_id WHERE vi.is_active=1 AND vc.is_correct=0"
    ).fetchall():
        text = (row["choice_text"] or "").strip()
        if text:
            active_distractors.add(text)

    active_lemmas: set[str] = set()
    for row in conn.execute("SELECT lemma FROM vocab_items WHERE is_active=1").fetchall():
        active_lemmas.add((row["lemma"] or "").strip())

    active_verb_count = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='verb'"
    ).fetchone()[0]
    active_verb_10k = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='verb' AND bin_name='10K'"
    ).fetchone()[0]
    active_noun_10k = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='noun' AND bin_name='10K'"
    ).fetchone()[0]
    active_adverb = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='adverb'"
    ).fetchone()[0]

    checks: list[tuple[str, str]] = []
    issues: list[str] = []

    # Check 1: target IDs match manifest
    if sorted(TARGET_IDS) == manifest_ids:
        checks.append(("Target IDs match manifest", "PASS"))
    else:
        diff = set(TARGET_IDS).symmetric_difference(set(manifest_ids))
        issues.append(f"Target ID mismatch: {diff}")
        checks.append(("Target IDs match manifest", f"FAIL: {diff}"))

    # Check 2: all 9 still is_active=0
    inactive_count = conn.execute(
        f"SELECT COUNT(*) FROM vocab_items WHERE id IN ({','.join(str(i) for i in TARGET_IDS)}) AND is_active=0"
    ).fetchone()[0]
    if inactive_count == 9:
        checks.append(("All 9 items still is_active=0", "PASS"))
    else:
        already_active = 9 - inactive_count
        issues.append(f"{already_active} items already active")
        checks.append(("All 9 items still is_active=0", f"FAIL: {already_active} already active"))

    # Per-item R1a, R1b, dup lemma, integrity checks
    item_details: list[dict] = []
    all_items_pass = True
    for item_id in TARGET_IDS:
        row = conn.execute(
            "SELECT lemma, pos, correct_answer, is_active, bin_name FROM vocab_items WHERE id=?",
            (item_id,)
        ).fetchone()
        if row is None:
            issues.append(f"item_id={item_id} NOT FOUND")
            all_items_pass = False
            continue

        ca = (row["correct_answer"] or "").strip()
        lemma = (row["lemma"] or "").strip()
        pos = (row["pos"] or "").strip()

        r1a = ca not in active_distractors
        dist_rows = conn.execute(
            "SELECT choice_text FROM vocab_choices WHERE item_id=? AND is_correct=0", (item_id,)
        ).fetchall()
        distractor_texts = [(r["choice_text"] or "").strip() for r in dist_rows]
        r1b_hits = [d for d in distractor_texts if d and d in active_cas]
        r1b = len(r1b_hits) == 0
        no_dup = lemma not in active_lemmas
        correct_ct = conn.execute(
            "SELECT COUNT(*) FROM vocab_choices WHERE item_id=? AND is_correct=1", (item_id,)
        ).fetchone()[0]
        total_ct = conn.execute(
            "SELECT COUNT(*) FROM vocab_choices WHERE item_id=?", (item_id,)
        ).fetchone()[0]
        integrity = correct_ct == 1 and total_ct >= 4

        item_pass = r1a and r1b and no_dup and integrity
        if not item_pass:
            all_items_pass = False
            if not r1a:
                issues.append(f"[{item_id}/{lemma}] R1a FAIL: CA='{ca}'")
            if not r1b:
                issues.append(f"[{item_id}/{lemma}] R1b FAIL: {r1b_hits}")
            if not no_dup:
                issues.append(f"[{item_id}/{lemma}] dup lemma")
            if not integrity:
                issues.append(f"[{item_id}/{lemma}] choice integrity: correct={correct_ct} total={total_ct}")

        item_details.append({
            "item_id": item_id, "lemma": lemma, "pos": pos, "ca": ca,
            "r1a": r1a, "r1b": r1b, "no_dup": no_dup, "integrity": integrity,
            "passes": item_pass,
        })

    if all_items_pass:
        checks.append(("All items pass R1a/R1b/dup/integrity", "PASS"))
    else:
        checks.append(("All items pass R1a/R1b/dup/integrity", "FAIL"))

    # Check 3: script only touches is_active for target IDs
    # Find all UPDATE statements in script SQL block
    sql_block = re.search(r"<<'SQL'(.*?)SQL", script_text, re.DOTALL)
    sql_content = sql_block.group(1) if sql_block else ""

    # No forbidden table references
    forbidden = []
    for word in ["sessions", "users", "vocab_attempts", "vocab_sessions",
                 "vocab_feedback", "noun", "adverb"]:
        if re.search(rf"\b{word}\b", sql_content, re.IGNORECASE):
            forbidden.append(word)
    if forbidden:
        issues.append(f"Forbidden tables/words in script SQL: {forbidden}")
        checks.append(("No forbidden tables in script", f"FAIL: {forbidden}"))
    else:
        checks.append(("No forbidden tables in script", "PASS"))

    # Only is_active column modified in SQL
    update_cols = re.findall(r"SET\s+(\w+)\s*=", sql_content, re.IGNORECASE)
    non_active_cols = [c for c in update_cols if c.lower() != "is_active"]
    if non_active_cols:
        issues.append(f"Script modifies unexpected columns: {non_active_cols}")
        checks.append(("Script only modifies is_active", f"FAIL: {non_active_cols}"))
    else:
        checks.append(("Script only modifies is_active", "PASS"))

    # IDs in script UPDATE match exactly the target set
    ids_in_script = set(int(x) for x in re.findall(r"\b(\d{3,5})\b", sql_content))
    ids_in_script = ids_in_script.intersection(set(range(1, 100000)))
    expected_ids = set(TARGET_IDS)
    if ids_in_script == expected_ids:
        checks.append(("Script UPDATE targets exactly match manifest IDs", "PASS"))
    else:
        diff = ids_in_script.symmetric_difference(expected_ids)
        issues.append(f"Script ID mismatch: {diff}")
        checks.append(("Script UPDATE targets exactly match manifest IDs", f"FAIL: {diff}"))

    conn.close()

    overall = "SAFE_TO_PROCEED" if not issues else "BLOCKED"

    # Write MD
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    lines = [
        "# Verb Tranche1 — Pre-Activation Safety Audit",
        "",
        f"**DB:** {DB_PATH}",
        f"**Date:** 2026-04-19",
        f"**Anchor commit:** cb19545",
        "",
        "## Check Results",
        "",
        "| Check | Result |",
        "|-------|--------|",
    ]
    for name, result in checks:
        lines.append(f"| {name} | {result} |")
    lines += [
        "",
        "## Target Items",
        "",
        "| item_id | lemma | pos | CA | R1a | R1b | no_dup | integrity | PASS |",
        "|---------|-------|-----|-----|-----|-----|--------|-----------|------|",
    ]
    for d in item_details:
        lines.append(
            f"| {d['item_id']} | {d['lemma']} | {d['pos']} | {d['ca']} "
            f"| {'✓' if d['r1a'] else 'FAIL'} "
            f"| {'✓' if d['r1b'] else 'FAIL'} "
            f"| {'✓' if d['no_dup'] else 'FAIL'} "
            f"| {'✓' if d['integrity'] else 'FAIL'} "
            f"| {'**PASS**' if d['passes'] else '**FAIL**'} |"
        )
    lines += [
        "",
        "## Current Bank State",
        "",
        f"- Active verbs (all bins): {active_verb_count}",
        f"- Active verbs (10K): {active_verb_10k}",
        f"- Active noun/10K: {active_noun_10k}",
        f"- Active adverbs: {active_adverb}",
        "",
        f"## Overall: **{overall}**",
        "",
    ]
    if issues:
        lines += ["## Issues", ""]
        for i in issues:
            lines.append(f"- {i}")

    md_path = os.path.join(OUTPUT_DIR, "verb_tranche1_preactivation_audit.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Console
    print("=" * 60)
    print("STAGE 1 — PRE-ACTIVATION SAFETY AUDIT")
    print("=" * 60)
    print(f"\nCurrent active verbs: {active_verb_count} (10K: {active_verb_10k})")
    print(f"Active noun/10K: {active_noun_10k}  |  Active adverbs: {active_adverb}")
    print()
    print("Target items:")
    for d in item_details:
        status = "PASS" if d["passes"] else "FAIL"
        print(f"  {status:<6} id={d['item_id']:<6} {d['lemma']:<15} CA={d['ca']}")
    print()
    print("Checks:")
    for name, result in checks:
        ok = "PASS" in result
        print(f"  {'OK' if ok else 'FAIL':4}  {name}: {result}")
    print()
    if issues:
        print("ISSUES:")
        for i in issues:
            print(f"  - {i}")
        print()
    print(f"Forbidden writes absent: {'YES' if not issues else 'NO'}")
    print(f"OVERALL: {overall}")
    print(f"\nArtifact: {md_path}")

    return 0 if overall == "SAFE_TO_PROCEED" else 1


if __name__ == "__main__":
    sys.exit(main())
