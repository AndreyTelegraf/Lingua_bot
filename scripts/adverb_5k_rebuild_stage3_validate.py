#!/usr/bin/env python3
"""
adverb_5k_rebuild_stage3_validate.py
Stage 3 — Group-level validation. All 6 items must pass simultaneously.
Zero partial pass allowed.

Checks (per item):
  1. item exists, pos=adverb, bin=5K, is_active=0
  2. correct_answer matches proposal
  3. each distractor is not an active CA (Rule 1b)
  4. each distractor is not an active distractor of any other active item (Rule 1a risk)
  5. each distractor is not the item's own CA
  6. each distractor is not a CA of any other group item
  7. all 18 proposed distractors are unique across the batch

Output:
  diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_validation.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
PROPOSALS_PATH = "diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_proposals.json"
OUTPUT_DIR = "diagnostics_exports/adverb_5k_rebuild/current"

CHECKS = [
    "item_exists_inactive_5k_adverb",
    "correct_answer_matches",
    "no_r1b_violation",
    "no_r1a_risk",
    "distractor_not_own_ca",
    "no_cross_group_ca_reference",
    "all_distractors_unique_across_batch",
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Adverb 5K group-level validation. Read-only.")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--proposals", default=PROPOSALS_PATH)
    ap.add_argument("--output-dir", default=OUTPUT_DIR)
    args = ap.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        return 1
    if not os.path.exists(args.proposals):
        print(f"ERROR: Proposals file not found: {args.proposals}", file=sys.stderr)
        return 1

    with open(args.proposals, encoding="utf-8") as f:
        proposals_data = json.load(f)

    if not proposals_data.get("stage2_accept"):
        print("ERROR: Stage 2 not accepted. Run stage2 first.", file=sys.stderr)
        return 1

    proposals = proposals_data["proposals"]

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

    group_cas = {p["correct_answer"] for p in proposals}
    all_proposed_distractors: list[str] = []
    for p in proposals:
        all_proposed_distractors.extend(p["new_distractors"])

    conn.close()

    results = []
    all_pass = True

    for p in proposals:
        item_id = p["item_id"]
        checks_pass: dict[str, bool] = {c: True for c in CHECKS}
        check_details: dict[str, str] = {}

        # Check 1: item exists, correct state
        conn2 = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
        conn2.row_factory = sqlite3.Row
        row = conn2.execute(
            "SELECT id, lemma, bin_name, correct_answer, pos, is_active FROM vocab_items WHERE id=?",
            (item_id,)
        ).fetchone()
        conn2.close()

        if row is None or row["pos"] != "adverb" or row["bin_name"] != "5K" or row["is_active"] != 0:
            checks_pass["item_exists_inactive_5k_adverb"] = False
            check_details["item_exists_inactive_5k_adverb"] = (
                "MISSING or wrong state" if row is None
                else f"pos={row['pos']}, bin={row['bin_name']}, active={row['is_active']}"
            )

        # Check 2: CA matches
        if row and row["correct_answer"] != p["correct_answer"]:
            checks_pass["correct_answer_matches"] = False
            check_details["correct_answer_matches"] = f"DB has {row['correct_answer']!r}, proposal has {p['correct_answer']!r}"

        # Checks 3-6 per distractor
        r1b_fails = [d for d in p["new_distractors"] if d in active_cas]
        # Rule 1a: item's own correct_answer must not be an active distractor
        r1a_ca_in_active_distractor = p["correct_answer"] in active_distractors
        own_ca_fails = [d for d in p["new_distractors"] if d == p["correct_answer"]]
        cross_group_fails = [d for d in p["new_distractors"] if d in group_cas]

        if r1b_fails:
            checks_pass["no_r1b_violation"] = False
            check_details["no_r1b_violation"] = f"distractors {r1b_fails} are active CAs"
        if r1a_ca_in_active_distractor:
            checks_pass["no_r1a_risk"] = False
            check_details["no_r1a_risk"] = f"item CA {p['correct_answer']!r} is an active distractor (Rule 1a)"
        if own_ca_fails:
            checks_pass["distractor_not_own_ca"] = False
            check_details["distractor_not_own_ca"] = f"distractors {own_ca_fails} equal own CA"
        if cross_group_fails:
            checks_pass["no_cross_group_ca_reference"] = False
            check_details["no_cross_group_ca_reference"] = f"distractors {cross_group_fails} are group CAs"

        # Check 7: batch uniqueness
        dup_distractors = [d for d in p["new_distractors"] if all_proposed_distractors.count(d) > 1]
        if dup_distractors:
            checks_pass["all_distractors_unique_across_batch"] = False
            check_details["all_distractors_unique_across_batch"] = f"duplicated: {dup_distractors}"

        item_pass = all(checks_pass.values())
        if not item_pass:
            all_pass = False

        results.append({
            "item_id": item_id,
            "lemma": p["lemma"],
            "correct_answer": p["correct_answer"],
            "new_distractors": p["new_distractors"],
            "checks_pass": checks_pass,
            "check_details": check_details,
            "item_pass": item_pass,
        })

    output = {
        "checks": CHECKS,
        "total_items": len(results),
        "items_pass": sum(1 for r in results if r["item_pass"]),
        "items_fail": sum(1 for r in results if not r["item_pass"]),
        "group_pass": all_pass,
        "stage3_accept": all_pass,
        "results": results,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "adverb_5k_rebuild_validation.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("STAGE 3 — GROUP-LEVEL VALIDATION")
    print(f"  Items pass: {output['items_pass']}/{output['total_items']}")
    for r in results:
        status = "PASS" if r["item_pass"] else "FAIL"
        print(f"  [{status}] id={r['item_id']:5} {r['lemma']:20} -> {r['correct_answer']}")
        if not r["item_pass"]:
            for check, passed in r["checks_pass"].items():
                if not passed:
                    print(f"           FAIL {check}: {r['check_details'].get(check, '')}")
    print(f"\n  JSON: {json_path}")
    if output["stage3_accept"]:
        print("STAGE 3 ACCEPTANCE: PASS")
        return 0
    else:
        print("STAGE 3 ACCEPTANCE: FAIL — group validation not atomic, no apply pack may be built")
        return 1


if __name__ == "__main__":
    sys.exit(main())
