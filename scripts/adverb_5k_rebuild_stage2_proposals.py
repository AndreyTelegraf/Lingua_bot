#!/usr/bin/env python3
"""
adverb_5k_rebuild_stage2_proposals.py
Stage 2 — Encode distractor rebuild proposals for the 6 inactive 5K adverb items.

Proposals are hardcoded (verified against active bank in prior session):
  - 3 distractors per item (total 4 choices: 1 CA + 3 distractors)
  - No distractor is an active correct_answer
  - No distractor is a CA of any group member
  - All distractors are unique across the batch
  - All distractors are valid single-word Russian adverbs

Outputs:
  diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_proposals.json
  diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_proposals.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
OUTPUT_DIR = "diagnostics_exports/adverb_5k_rebuild/current"

# Verified proposals: each item gets exactly 3 new distractors.
# All 18 distractor words are unique across the batch.
PROPOSALS = [
    {
        "item_id": 3958,
        "lemma": "frequentemente",
        "correct_answer": "часто",
        "new_distractors": ["редко", "иногда", "давно"],
    },
    {
        "item_id": 3960,
        "lemma": "geralmente",
        "correct_answer": "обычно",
        "new_distractors": ["постепенно", "сначала", "раньше"],
    },
    {
        "item_id": 10017,
        "lemma": "novamente",
        "correct_answer": "снова",
        "new_distractors": ["сразу", "впервые", "вдруг"],
    },
    {
        "item_id": 3963,
        "lemma": "principalmente",
        "correct_answer": "главным образом",
        "new_distractors": ["всё-таки", "совсем", "тоже"],
    },
    {
        "item_id": 10019,
        "lemma": "exatamente",
        "correct_answer": "точно",
        "new_distractors": ["слегка", "немного", "едва"],
    },
    {
        "item_id": 3970,
        "lemma": "facilmente",
        "correct_answer": "легко",
        "new_distractors": ["трудно", "тихо", "крепко"],
    },
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Adverb 5K distractor proposals. Read-only DB check.")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--output-dir", default=OUTPUT_DIR)
    args = ap.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    active_cas: set[str] = set(
        r[0] for r in conn.execute(
            "SELECT correct_answer FROM vocab_items WHERE is_active=1 AND correct_answer IS NOT NULL"
        ).fetchall()
    )
    conn.close()

    group_cas = {p["correct_answer"] for p in PROPOSALS}
    all_proposed_distractors: list[str] = []
    for p in PROPOSALS:
        all_proposed_distractors.extend(p["new_distractors"])

    enriched = []
    errors = []

    for p in PROPOSALS:
        item_errors = []

        # Rule: no distractor equals the item's own CA
        for d in p["new_distractors"]:
            if d == p["correct_answer"]:
                item_errors.append(f"distractor {d!r} equals own CA")

        # Rule 1b: no distractor is an active CA
        for d in p["new_distractors"]:
            if d in active_cas:
                item_errors.append(f"distractor {d!r} is an active CA (Rule 1b violation)")

        # Rule: no distractor is a group CA
        for d in p["new_distractors"]:
            if d in group_cas:
                item_errors.append(f"distractor {d!r} is a group CA (cross-group reference)")

        # Uniqueness check across full batch
        for d in p["new_distractors"]:
            if all_proposed_distractors.count(d) > 1:
                item_errors.append(f"distractor {d!r} appears in multiple items")

        if item_errors:
            errors.extend([f"id={p['item_id']} ({p['lemma']}): {e}" for e in item_errors])

        enriched.append({
            **p,
            "total_choices": 4,
            "item_errors": item_errors,
        })

    os.makedirs(args.output_dir, exist_ok=True)

    output = {
        "total_items": len(enriched),
        "total_new_distractors": len(all_proposed_distractors),
        "unique_distractors": len(set(all_proposed_distractors)),
        "validation_errors": errors,
        "stage2_accept": len(errors) == 0,
        "proposals": enriched,
    }

    json_path = os.path.join(args.output_dir, "adverb_5k_rebuild_proposals.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    csv_path = os.path.join(args.output_dir, "adverb_5k_rebuild_proposals.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["item_id", "lemma", "correct_answer", "distractor_1", "distractor_2", "distractor_3", "errors"])
        for p in enriched:
            d = p["new_distractors"]
            writer.writerow([
                p["item_id"], p["lemma"], p["correct_answer"],
                d[0], d[1], d[2],
                "; ".join(p["item_errors"]) if p["item_errors"] else "",
            ])

    print("STAGE 2 — DISTRACTOR REBUILD PROPOSALS")
    print(f"  Items: {len(enriched)}")
    print(f"  Total new distractors: {len(all_proposed_distractors)} ({len(set(all_proposed_distractors))} unique)")
    for p in enriched:
        status = "OK" if not p["item_errors"] else "ERROR"
        print(f"  [{status}] id={p['item_id']:5} {p['lemma']:20} -> {p['correct_answer']}")
        print(f"           distractors: {p['new_distractors']}")
    if errors:
        print("\n  ERRORS:")
        for e in errors:
            print(f"    {e}")
    print(f"\n  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")
    if output["stage2_accept"]:
        print("STAGE 2 ACCEPTANCE: PASS")
        return 0
    else:
        print("STAGE 2 ACCEPTANCE: FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
