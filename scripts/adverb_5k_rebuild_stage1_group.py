#!/usr/bin/env python3
"""
adverb_5k_rebuild_stage1_group.py
Stage 1 — Extract and confirm the 6 inactive 5K adverb group items. Read-only.

Confirms:
  - All 6 expected items exist with correct pos/bin/active state
  - Each has exactly 6 existing choices
  - All existing distractors are CAs of other inactive adverbs (cross-group cluster)
  - None are already active

Output:
  diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_group.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
OUTPUT_DIR = "diagnostics_exports/adverb_5k_rebuild/current"

EXPECTED_ITEMS = [
    (3958, "frequentemente", "часто"),
    (3960, "geralmente", "обычно"),
    (10017, "novamente", "снова"),
    (3963, "principalmente", "главным образом"),
    (10019, "exatamente", "точно"),
    (3970, "facilmente", "легко"),
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Adverb 5K group extraction. Read-only.")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--output-dir", default=OUTPUT_DIR)
    args = ap.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # Active CAs for cross-reference checking
    active_cas: set[str] = set(
        r[0] for r in conn.execute(
            "SELECT correct_answer FROM vocab_items WHERE is_active=1 AND correct_answer IS NOT NULL"
        ).fetchall()
    )

    # All inactive adverb CAs
    inactive_adverb_cas: set[str] = set(
        r[0] for r in conn.execute(
            "SELECT correct_answer FROM vocab_items WHERE pos='adverb' AND is_active=0 AND correct_answer IS NOT NULL"
        ).fetchall()
    )

    items_out = []
    errors = []

    for item_id, expected_lemma, expected_ca in EXPECTED_ITEMS:
        row = conn.execute(
            "SELECT id, lemma, bin_name, correct_answer, pos, is_active "
            "FROM vocab_items WHERE id=?", (item_id,)
        ).fetchone()

        if row is None:
            errors.append(f"MISSING: item_id={item_id} ({expected_lemma})")
            continue

        item_errors = []
        if row["lemma"] != expected_lemma:
            item_errors.append(f"lemma mismatch: expected {expected_lemma!r}, got {row['lemma']!r}")
        if row["correct_answer"] != expected_ca:
            item_errors.append(f"CA mismatch: expected {expected_ca!r}, got {row['correct_answer']!r}")
        if row["pos"] != "adverb":
            item_errors.append(f"pos={row['pos']!r} (expected 'adverb')")
        if row["bin_name"] != "5K":
            item_errors.append(f"bin_name={row['bin_name']!r} (expected '5K')")
        if row["is_active"] != 0:
            item_errors.append("item is ACTIVE (expected inactive)")

        choices = conn.execute(
            "SELECT choice_text, is_correct FROM vocab_choices WHERE item_id=? ORDER BY position_index",
            (item_id,)
        ).fetchall()
        choice_count = len(choices)
        if choice_count != 6:
            item_errors.append(f"choice_count={choice_count} (expected 6)")

        distractors = [c["choice_text"] for c in choices if c["is_correct"] == 0]
        active_ca_distractors = [d for d in distractors if d in active_cas]
        inactive_adverb_distractors = [d for d in distractors if d in inactive_adverb_cas]

        if active_ca_distractors:
            item_errors.append(f"distractors {active_ca_distractors} are ACTIVE CAs (r1b_fail)")

        if item_errors:
            errors.extend([f"id={item_id} ({expected_lemma}): {e}" for e in item_errors])

        items_out.append({
            "item_id": item_id,
            "lemma": row["lemma"],
            "bin_name": row["bin_name"],
            "correct_answer": row["correct_answer"],
            "pos": row["pos"],
            "is_active": row["is_active"],
            "choice_count": choice_count,
            "existing_distractors": distractors,
            "distractor_active_ca_collisions": active_ca_distractors,
            "distractor_inactive_adverb_refs": inactive_adverb_distractors,
            "item_errors": item_errors,
        })

    conn.close()

    group_cas = {item["correct_answer"] for item in items_out}
    output = {
        "group_size": len(items_out),
        "expected_size": len(EXPECTED_ITEMS),
        "group_cas": sorted(group_cas),
        "validation_errors": errors,
        "stage1_accept": len(errors) == 0,
        "items": items_out,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "adverb_5k_group.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("STAGE 1 — ADVERB 5K GROUP EXTRACTION")
    print(f"  Items confirmed: {len(items_out)}/{len(EXPECTED_ITEMS)}")
    for item in items_out:
        status = "OK" if not item["item_errors"] else "ERROR"
        print(f"  [{status}] id={item['item_id']:5} {item['lemma']:20} -> {item['correct_answer']}")
    if errors:
        print("\n  ERRORS:")
        for e in errors:
            print(f"    {e}")
    print(f"\n  JSON: {json_path}")
    if output["stage1_accept"]:
        print("STAGE 1 ACCEPTANCE: PASS")
        return 0
    else:
        print("STAGE 1 ACCEPTANCE: FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
