#!/usr/bin/env python3
"""
adverb_5k_rebuild_live_validate.py
Stage 3 — Live atomic validation against staging DB after apply.

Checks per item:
  1. item_still_inactive       — is_active=0
  2. exactly_4_choices         — choice_count == 4
  3. exactly_1_correct         — exactly 1 is_correct=1 row
  4. correct_answer_unchanged  — correct choice_text matches manifest CA
  5. rule_1b_pass              — no distractor is an active CA
  6. rule_1a_pass              — item's own CA is not an active distractor
  7. no_cross_group_distractor — no distractor is a CA of another group item

Group-level check:
  8. manifest_exact_match      — live choices exactly match manifest inserts
  9. no_mutual_collision       — all 18 distractors across group are unique

Outputs:
  diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_live_validation.json
  diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_live_validation.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
MANIFEST_PATH = "diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_manifest.json"
OUTPUT_DIR = "diagnostics_exports/adverb_5k_rebuild/current"

PER_ITEM_CHECKS = [
    "item_still_inactive",
    "exactly_4_choices",
    "exactly_1_correct",
    "correct_answer_unchanged",
    "rule_1b_pass",
    "rule_1a_pass",
    "no_cross_group_distractor",
]
GROUP_CHECKS = [
    "manifest_exact_match",
    "no_mutual_collision",
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Live atomic validation. Read-only.")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--manifest", default=MANIFEST_PATH)
    ap.add_argument("--output-dir", default=OUTPUT_DIR)
    args = ap.parse_args(argv)

    for path in [args.db, args.manifest]:
        if not os.path.exists(path):
            print(f"ERROR: not found: {path}", file=sys.stderr)
            return 1

    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    active_cas: set[str] = set(
        r[0] for r in conn.execute(
            "SELECT correct_answer FROM vocab_items WHERE is_active=1 AND correct_answer IS NOT NULL"
        ).fetchall()
    )
    active_distractors: set[str] = set(
        r[0] for r in conn.execute(
            "SELECT DISTINCT vc.choice_text FROM vocab_choices vc "
            "JOIN vocab_items vi ON vi.id=vc.item_id WHERE vi.is_active=1 AND vc.is_correct=0"
        ).fetchall()
    )

    group_cas = {op["correct_answer"] for op in manifest["operations"]}

    results = []
    all_distractors_used: list[str] = []

    for op in manifest["operations"]:
        item_id = op["item_id"]
        expected_ca = op["correct_answer"]
        expected_distractors = [i["choice_text"] for i in op["inserts"] if i["is_correct"] == 0]

        row = conn.execute(
            "SELECT id, lemma, bin_name, pos, is_active, correct_answer FROM vocab_items WHERE id=?",
            (item_id,)
        ).fetchone()
        choices = conn.execute(
            "SELECT choice_text, is_correct FROM vocab_choices WHERE item_id=? ORDER BY position_index",
            (item_id,)
        ).fetchall()

        checks_pass: dict[str, bool] = {c: True for c in PER_ITEM_CHECKS}
        check_details: dict[str, str] = {}

        live_distractors = [c["choice_text"] for c in choices if c["is_correct"] == 0]
        live_correct = [c["choice_text"] for c in choices if c["is_correct"] == 1]
        choice_count = len(choices)

        # Check 1: still inactive
        if row is None or row["is_active"] != 0:
            checks_pass["item_still_inactive"] = False
            check_details["item_still_inactive"] = "NOT FOUND" if row is None else f"is_active={row['is_active']}"

        # Check 2: exactly 4 choices
        if choice_count != 4:
            checks_pass["exactly_4_choices"] = False
            check_details["exactly_4_choices"] = f"choice_count={choice_count}"

        # Check 3: exactly 1 correct
        if len(live_correct) != 1:
            checks_pass["exactly_1_correct"] = False
            check_details["exactly_1_correct"] = f"correct_count={len(live_correct)}"

        # Check 4: correct answer unchanged
        if not live_correct or live_correct[0] != expected_ca:
            checks_pass["correct_answer_unchanged"] = False
            check_details["correct_answer_unchanged"] = (
                f"live CA={live_correct[0]!r}, expected={expected_ca!r}"
                if live_correct else f"no correct choice found"
            )

        # Check 5: Rule 1b — no distractor is active CA
        r1b_fails = [d for d in live_distractors if d in active_cas]
        if r1b_fails:
            checks_pass["rule_1b_pass"] = False
            check_details["rule_1b_pass"] = f"distractors {r1b_fails} are active CAs"

        # Check 6: Rule 1a — item CA not an active distractor
        if live_correct and live_correct[0] in active_distractors:
            checks_pass["rule_1a_pass"] = False
            check_details["rule_1a_pass"] = f"CA {live_correct[0]!r} is an active distractor"

        # Check 7: no cross-group distractor
        cross_group = [d for d in live_distractors if d in group_cas]
        if cross_group:
            checks_pass["no_cross_group_distractor"] = False
            check_details["no_cross_group_distractor"] = f"distractors {cross_group} are group CAs"

        all_distractors_used.extend(live_distractors)

        item_pass = all(checks_pass.values())
        results.append({
            "item_id": item_id,
            "lemma": op["lemma"],
            "correct_answer": expected_ca,
            "live_choices": [{"choice_text": c["choice_text"], "is_correct": c["is_correct"]} for c in choices],
            "checks_pass": checks_pass,
            "check_details": check_details,
            "item_pass": item_pass,
        })

    conn.close()

    # Group checks
    group_checks_pass: dict[str, bool] = {c: True for c in GROUP_CHECKS}
    group_check_details: dict[str, str] = {}

    # Check 8: manifest exact match
    manifest_mismatches = []
    for op, result in zip(manifest["operations"], results):
        expected_choices = {i["choice_text"] for i in op["inserts"]}
        live_choices = {c["choice_text"] for c in result["live_choices"]}
        if expected_choices != live_choices:
            manifest_mismatches.append(
                f"id={op['item_id']}: expected={sorted(expected_choices)}, live={sorted(live_choices)}"
            )
    if manifest_mismatches:
        group_checks_pass["manifest_exact_match"] = False
        group_check_details["manifest_exact_match"] = "; ".join(manifest_mismatches)

    # Check 9: all 18 distractors unique across group
    dup_distractors = [d for d in set(all_distractors_used) if all_distractors_used.count(d) > 1]
    if dup_distractors:
        group_checks_pass["no_mutual_collision"] = False
        group_check_details["no_mutual_collision"] = f"duplicated distractors: {dup_distractors}"

    items_pass = sum(1 for r in results if r["item_pass"])
    group_pass = all(group_checks_pass.values()) and items_pass == len(results)
    stage3_accept = group_pass

    output = {
        "total_items": len(results),
        "items_pass": items_pass,
        "items_fail": len(results) - items_pass,
        "group_checks_pass": group_checks_pass,
        "group_check_details": group_check_details,
        "group_pass": group_pass,
        "stage3_accept": stage3_accept,
        "results": results,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "adverb_5k_rebuild_live_validation.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Markdown report
    md_lines = [
        "# Adverb 5K Rebuild — Live Atomic Validation",
        "",
        f"**Group result: {'PASS' if group_pass else 'FAIL'}**",
        f"**Items: {items_pass}/{len(results)} pass**",
        "",
        "## Per-Item Results",
        "",
        "| item_id | lemma | CA | " + " | ".join(PER_ITEM_CHECKS) + " | result |",
        "|---------|-------|-----|" + "|".join(["---"] * len(PER_ITEM_CHECKS)) + "|--------|",
    ]
    for r in results:
        check_cols = " | ".join("✓" if r["checks_pass"][c] else "✗" for c in PER_ITEM_CHECKS)
        status = "**PASS**" if r["item_pass"] else "**FAIL**"
        md_lines.append(f"| {r['item_id']} | {r['lemma']} | {r['correct_answer']} | {check_cols} | {status} |")

    md_lines += [
        "",
        "## Group Checks",
        "",
        "| Check | Result | Detail |",
        "|-------|--------|--------|",
    ]
    for c in GROUP_CHECKS:
        status = "✓ PASS" if group_checks_pass[c] else "✗ FAIL"
        detail = group_check_details.get(c, "OK")
        md_lines.append(f"| {c} | {status} | {detail} |")

    md_lines += [
        "",
        "## Live Choices Per Item",
        "",
    ]
    for r in results:
        md_lines.append(f"### id={r['item_id']} {r['lemma']} → {r['correct_answer']}")
        md_lines.append("")
        md_lines.append("| choice_text | is_correct |")
        md_lines.append("|-------------|------------|")
        for c in r["live_choices"]:
            md_lines.append(f"| {c['choice_text']} | {c['is_correct']} |")
        md_lines.append("")

    md_path = os.path.join(args.output_dir, "adverb_5k_rebuild_live_validation.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print("STAGE 3 — LIVE ATOMIC VALIDATION")
    print(f"  Items pass: {items_pass}/{len(results)}")
    for r in results:
        status = "PASS" if r["item_pass"] else "FAIL"
        print(f"  [{status}] id={r['item_id']:5} {r['lemma']:20} -> {r['correct_answer']}")
        if not r["item_pass"]:
            for c, passed in r["checks_pass"].items():
                if not passed:
                    print(f"           FAIL {c}: {r['check_details'].get(c, '')}")
    print()
    print("  Group checks:")
    for c in GROUP_CHECKS:
        status = "PASS" if group_checks_pass[c] else "FAIL"
        detail = group_check_details.get(c, "OK")
        print(f"  [{status}] {c}: {detail}")
    print(f"\n  JSON: {json_path}")
    print(f"  MD:   {md_path}")
    if stage3_accept:
        print("STAGE 3 ACCEPTANCE: PASS")
        return 0
    else:
        print("STAGE 3 ACCEPTANCE: FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
