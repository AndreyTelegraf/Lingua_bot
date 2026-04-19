#!/usr/bin/env python3
"""
verb_tranche1_target_reconfirm.py
Stage 1 — Target set reconfirmation. Read-only.
Outputs: diagnostics_exports/verb_tranche1/current/verb_tranche1_target_reconfirmation.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
LIVE_VALIDATION_PATH = "diagnostics_exports/verb_tranche1/current/remediation_live_validation.json"
OUTPUT_DIR = "diagnostics_exports/verb_tranche1/current"

TARGET_IDS = [868, 921, 1732, 1759, 2172, 3467, 3491, 3509, 9328]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    with open(LIVE_VALIDATION_PATH) as f:
        prior_validation = json.load(f)
    prior_by_id = {r["item_id"]: r for r in prior_validation["items"]}

    # Active bank sets
    active_cas: set[str] = set()
    active_ca_map: dict[str, int] = {}
    for row in conn.execute(
        "SELECT id, correct_answer FROM vocab_items WHERE is_active=1 AND correct_answer IS NOT NULL"
    ).fetchall():
        ca = (row["correct_answer"] or "").strip()
        if ca:
            active_cas.add(ca)
            active_ca_map[ca] = row["id"]

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

    active_count = conn.execute("SELECT COUNT(*) FROM vocab_items WHERE is_active=1").fetchone()[0]

    items = []
    issues: list[str] = []

    for item_id in TARGET_IDS:
        row = conn.execute(
            "SELECT id, lemma, pos, correct_answer, is_active, bin_name FROM vocab_items WHERE id=?",
            (item_id,)
        ).fetchone()
        if row is None:
            issues.append(f"item_id={item_id} NOT FOUND in DB")
            items.append({"item_id": item_id, "error": "NOT_FOUND"})
            continue

        lemma = (row["lemma"] or "").strip()
        pos = (row["pos"] or "").strip()
        ca = (row["correct_answer"] or "").strip()
        is_active = row["is_active"]
        bin_name = (row["bin_name"] or "").strip()
        status = "n/a"

        item_checks: dict[str, object] = {}
        item_issues: list[str] = []

        # exists
        item_checks["exists"] = True

        # pos=verb
        item_checks["pos_verb"] = pos == "verb"
        if pos != "verb":
            item_issues.append(f"pos='{pos}' (expected 'verb')")

        # is_active=0
        item_checks["is_active_zero"] = is_active == 0
        if is_active != 0:
            item_issues.append(f"is_active={is_active} (expected 0)")

        # no dup lemma in active bank
        item_checks["no_dup_lemma"] = lemma not in active_lemmas
        if lemma in active_lemmas:
            item_issues.append(f"lemma '{lemma}' already active")

        # R1a: CA not in active distractors
        item_checks["r1a_pass"] = ca not in active_distractors
        if ca in active_distractors:
            item_issues.append(f"R1a FAIL: CA '{ca}' in active distractors")

        # Fetch distractors
        dist_rows = conn.execute(
            "SELECT id, choice_text FROM vocab_choices WHERE item_id=? AND is_correct=0",
            (item_id,)
        ).fetchall()
        distractor_texts = [(r["choice_text"] or "").strip() for r in dist_rows]

        # R1b: no distractor in active CAs
        r1b_hits = [d for d in distractor_texts if d and d in active_cas]
        item_checks["r1b_pass"] = len(r1b_hits) == 0
        if r1b_hits:
            item_issues.append(f"R1b FAIL: distractors in active CAs: {r1b_hits}")

        # Choice integrity: exactly 1 correct choice
        correct_rows = conn.execute(
            "SELECT COUNT(*) FROM vocab_choices WHERE item_id=? AND is_correct=1", (item_id,)
        ).fetchone()[0]
        total_choices = conn.execute(
            "SELECT COUNT(*) FROM vocab_choices WHERE item_id=?", (item_id,)
        ).fetchone()[0]
        item_checks["correct_choice_count"] = correct_rows == 1
        item_checks["total_choices"] = total_choices
        if correct_rows != 1:
            item_issues.append(f"correct_choice count={correct_rows} (expected 1)")
        if total_choices < 4:
            item_issues.append(f"total_choices={total_choices} (expected >=4)")

        # Consistent with prior validation
        prior = prior_by_id.get(item_id, {})
        prior_passed = prior.get("passes", False)
        item_checks["consistent_with_prior_validation"] = prior_passed
        if not prior_passed:
            item_issues.append("prior live validation did not pass")

        passes = len(item_issues) == 0
        if item_issues:
            issues.extend([f"[{item_id}/{lemma}] {i}" for i in item_issues])

        items.append({
            "item_id": item_id,
            "lemma": lemma,
            "pos": pos,
            "bin_name": bin_name,
            "status": status,
            "correct_answer": ca,
            "is_active": is_active,
            "total_choices": total_choices,
            "correct_choices": correct_rows,
            "distractor_count": len(distractor_texts),
            "checks": item_checks,
            "item_issues": item_issues,
            "passes": passes,
        })

    conn.close()

    pass_count = sum(1 for i in items if i.get("passes"))
    fail_count = len(items) - pass_count
    overall = "CONFIRMED" if not issues else "BLOCKED"

    # Write MD
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    lines = [
        "# Verb Tranche1 — Target Set Reconfirmation",
        "",
        f"**DB:** {args.db}",
        f"**Date:** 2026-04-19",
        f"**Active bank size:** {active_count} items",
        "",
        "## Target Items",
        "",
        "| item_id | lemma | pos | bin | CA | is_active | choices | R1a | R1b | no_dup | PASS |",
        "|---------|-------|-----|-----|----|-----------|---------|-----|-----|--------|------|",
    ]
    for item in items:
        if "error" in item:
            lines.append(f"| {item['item_id']} | — | — | — | — | — | — | — | — | — | FAIL({item['error']}) |")
            continue
        c = item["checks"]
        lines.append(
            f"| {item['item_id']} | {item['lemma']} | {item['pos']} | {item['bin_name']} "
            f"| {item['correct_answer']} | {item['is_active']} "
            f"| {item['total_choices']} "
            f"| {'✓' if c.get('r1a_pass') else 'FAIL'} "
            f"| {'✓' if c.get('r1b_pass') else 'FAIL'} "
            f"| {'✓' if c.get('no_dup_lemma') else 'FAIL'} "
            f"| {'**PASS**' if item['passes'] else '**FAIL**'} |"
        )
    lines += [
        "",
        f"## Summary: {pass_count}/{len(items)} PASS",
        "",
        f"## Overall: **{overall}**",
        "",
    ]
    if issues:
        lines += ["## Issues", ""]
        for i in issues:
            lines.append(f"- {i}")

    md_path = os.path.join(OUTPUT_DIR, "verb_tranche1_target_reconfirmation.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Console
    print("=" * 60)
    print("STAGE 1 — TARGET SET RECONFIRMATION")
    print("=" * 60)
    print(f"\nActive bank: {active_count} items")
    print()
    for item in items:
        if "error" in item:
            print(f"  FAIL   id={item['item_id']} NOT_FOUND")
            continue
        status = "PASS" if item["passes"] else "FAIL"
        print(
            f"  {status:<6} id={item['item_id']:<6} {item['lemma']:<15} "
            f"bin={item['bin_name']:<5} CA={item['correct_answer']}"
        )
    print()
    print(f"PASS: {pass_count}/{len(items)}")
    if issues:
        print("ISSUES:")
        for i in issues:
            print(f"  - {i}")
    print(f"\nOVERALL: {overall}")
    print(f"\nArtifact: {md_path}")

    return 0 if overall == "CONFIRMED" else 1


if __name__ == "__main__":
    sys.exit(main())
