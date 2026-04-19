#!/usr/bin/env python3
"""
verb_choice_repair_stage3_validate.py
Stage 3 — Validation of proposed repairs.
Read-only. Validates structural and Rule 1 compliance for READY proposals.

Checks per READY item:
  - exactly 4 choices (1 correct + 3 distractors)
  - exactly 1 correct choice
  - Rule 1a: item CA not in active distractors
  - Rule 1b: none of item distractors in active correct_answers
  - no duplicate distractors within item
  - no distractor equals the item's correct_answer
  - no duplicate lemma vs active bank

Outputs:
  diagnostics_exports/verb_choice_repair/current/verb_choice_repair_validation.json
  diagnostics_exports/verb_choice_repair/current/verb_choice_repair_validation_summary.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
PROPOSALS_JSON = "diagnostics_exports/verb_choice_repair/current/verb_choice_repair_proposals.json"
OUTPUT_DIR = "diagnostics_exports/verb_choice_repair/current"


def _validate_item(item: dict, active_cas: set, active_distractors: set, active_lemmas: set) -> dict:
    item_id = item["item_id"]
    lemma = item["lemma"]
    ca = item["correct_answer"] or ""
    d1 = item.get("proposed_distractor_1") or ""
    d2 = item.get("proposed_distractor_2") or ""
    d3 = item.get("proposed_distractor_3") or ""

    choices = [ca, d1, d2, d3]
    distractors = [d1, d2, d3]

    failures: list[str] = []

    # 4 choices, 1 correct
    if len(choices) != 4:
        failures.append(f"choice_count={len(choices)} (expected 4)")
    blank_choices = [c for c in choices if not c]
    if blank_choices:
        failures.append(f"blank_choices: {len(blank_choices)} blank entries")

    # Rule 1a: CA must not be an active distractor
    if ca and ca in active_distractors:
        failures.append(f"r1a_fail: CA '{ca}' is already a distractor in active bank")

    # Rule 1b: distractors must not be active CAs
    r1b_hits = [d for d in distractors if d and d in active_cas]
    if r1b_hits:
        failures.append(f"r1b_fail: distractors {r1b_hits} are active correct_answers")

    # No dup within item
    non_empty = [c for c in choices if c]
    if len(set(non_empty)) < len(non_empty):
        failures.append("dup_within_item: duplicate values in choice set")

    # Distractors must not equal CA
    ca_in_dist = [d for d in distractors if d and d == ca]
    if ca_in_dist:
        failures.append(f"distractor_equals_ca: {ca_in_dist}")

    # No dup lemma vs active bank
    if lemma in active_lemmas:
        failures.append(f"dup_lemma: '{lemma}' already active in bank")

    return {
        "item_id": item_id,
        "lemma": lemma,
        "correct_answer": ca,
        "distractors": [d1, d2, d3],
        "checks_run": 7,
        "failures": failures,
        "passes": len(failures) == 0,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 3: validate proposed repairs. Read-only.")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--proposals", default=PROPOSALS_JSON)
    ap.add_argument("--output-dir", default=OUTPUT_DIR)
    args = ap.parse_args(argv)

    for path, label in [(args.db, "DB"), (args.proposals, "proposals JSON")]:
        if not os.path.exists(path):
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            return 1

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
    active_lemmas: set[str] = set(
        r[0] for r in conn.execute(
            "SELECT DISTINCT lemma FROM vocab_items WHERE is_active=1 AND pos='verb'"
        ).fetchall()
    )
    conn.close()

    with open(args.proposals, encoding="utf-8") as f:
        proposals_data = json.load(f)

    ready_items = [p for p in proposals_data["proposals"] if p["proposal_status"] == "READY"]
    review_items = [p for p in proposals_data["proposals"] if p["proposal_status"] == "REVIEW"]
    reject_items = [p for p in proposals_data["proposals"] if p["proposal_status"] == "REJECT"]

    validation_results = []
    for item in ready_items:
        result = _validate_item(item, active_cas, active_distractors, active_lemmas)
        validation_results.append(result)

    validated_ready = sum(1 for r in validation_results if r["passes"])
    failed = [r for r in validation_results if not r["passes"]]

    # Group failure reasons
    failure_groups: dict[str, list[int]] = {}
    for r in failed:
        for f in r["failures"]:
            key = f.split(":")[0]
            failure_groups.setdefault(key, []).append(r["item_id"])

    output = {
        "total_proposals": proposals_data["total"],
        "ready_proposals": len(ready_items),
        "review_proposals": len(review_items),
        "reject_proposals": len(reject_items),
        "validated_ready_count": validated_ready,
        "validation_failed_count": len(failed),
        "failure_groups": failure_groups,
        "review_items_summary": [
            {"item_id": p["item_id"], "lemma": p["lemma"], "reason": p.get("reject_reason", "")}
            for p in review_items
        ],
        "validation_results": validation_results,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "verb_choice_repair_validation.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    md_lines = [
        "# Verb Choice Repair — Stage 3: Validation",
        "",
        f"**DB:** {args.db}",
        "",
        "## Summary",
        "",
        "| Category | Count |",
        "|----------|-------|",
        f"| Total proposals | {proposals_data['total']} |",
        f"| READY proposals | {len(ready_items)} |",
        f"| REVIEW proposals | {len(review_items)} |",
        f"| REJECT proposals | {len(reject_items)} |",
        f"| Validated READY (pass all checks) | **{validated_ready}** |",
        f"| Validation failed | {len(failed)} |",
        "",
        "## Validation Results (READY items only)",
        "",
        "| item_id | lemma | CA | Distractors | PASS |",
        "|---------|-------|-----|-------------|------|",
    ]
    for r in validation_results:
        d_str = "/".join(r["distractors"])
        status = "**PASS**" if r["passes"] else f"**FAIL** ({'; '.join(r['failures'])})"
        md_lines.append(
            f"| {r['item_id']} | {r['lemma']} | {r['correct_answer']} | {d_str} | {status} |"
        )

    md_lines += [
        "",
        "## REVIEW Items (require bank surgery before activation)",
        "",
        "| item_id | lemma | CA | Blocker |",
        "|---------|-------|-----|---------|",
    ]
    for p in review_items:
        md_lines.append(
            f"| {p['item_id']} | {p['lemma']} | {p['correct_answer']} "
            f"| {p.get('reject_reason', '')[:80]} |"
        )

    if failure_groups:
        md_lines += ["", "## Failure Group Summary", ""]
        for key, ids in failure_groups.items():
            md_lines.append(f"- `{key}`: {ids}")

    md_lines += [
        "",
        f"**Recoverable now (READY + pass all checks): {validated_ready}**",
        f"**Recoverable with bank fix (REVIEW): {len(review_items)}**",
        f"**Irrecoverable in this workstream (REJECT): {len(reject_items)}**",
    ]

    md_path = os.path.join(args.output_dir, "verb_choice_repair_validation_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"STAGE 3 — VALIDATION OF PROPOSED REPAIRS")
    print(f"  Total proposals:         {proposals_data['total']}")
    print(f"  READY proposals:         {len(ready_items)}")
    print(f"  REVIEW proposals:        {len(review_items)}")
    print(f"  REJECT proposals:        {len(reject_items)}")
    print(f"  Validated READY:         {validated_ready}")
    print(f"  Validation failures:     {len(failed)}")
    if failure_groups:
        print(f"  Failure groups:          {list(failure_groups.keys())}")
    for r in validation_results:
        status = "PASS" if r["passes"] else f"FAIL {r['failures']}"
        print(f"    id={r['item_id']} {r['lemma']}: {status}")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")
    print(f"STAGE 3 ACCEPTANCE: {'PASS' if validated_ready > 0 else 'FAIL — no items validated'}")
    return 0 if validated_ready > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
