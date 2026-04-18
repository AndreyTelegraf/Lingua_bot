#!/usr/bin/env python3
"""
verb_tranche1_remediation_validate.py

STAGE 3 — Read-only post-remediation collision check.
Simulates the post-apply state using proposal JSON (no DB writes).
Produces:
  verb_tranche1_post_remediation_collision_report.json
  verb_tranche1_post_remediation_manifest.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
PROPOSALS_JSON = "diagnostics_exports/verb_tranche1/current/verb_tranche1_remediation_proposals.json"
OUTPUT_DIR = "diagnostics_exports/verb_tranche1/current"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    with open(PROPOSALS_JSON) as f:
        proposals = json.load(f)

    # Build active bank sets (unchanged)
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

    # Build proposed final state per item
    item_results = []
    tranche_cas: set[str] = set()
    tranche_distractors: set[str] = set()

    for prop in proposals:
        item_id = prop["item_id"]
        lemma = prop["lemma"]
        bin_name = prop["bin_name"]
        chosen_ca = (prop["chosen_ca"] or "").strip()

        # Derive final distractor set from proposals
        final_distractors: list[str] = []
        for dp in prop["distractor_proposals"]:
            final_distractors.append((dp["replacement"] or "").strip())

        # --- Rule checks against active bank ---

        # Duplicate lemma
        dup_row = conn.execute(
            "SELECT id FROM vocab_items WHERE lemma=? AND is_active=1", (lemma,)
        ).fetchone()
        dup_fail = dup_row is not None

        # R1a: CA must not be in active distractors
        r1a_fail = chosen_ca in active_distractors

        # R1b: no distractor may be in active CAs
        r1b_hits = [d for d in final_distractors if d and d in active_cas]
        r1b_fail = bool(r1b_hits)

        # --- Intra-tranche conflict check ---
        intra_ca_conflict = chosen_ca in tranche_distractors
        intra_dist_conflict = [d for d in final_distractors if d in tranche_cas]

        passes = not dup_fail and not r1a_fail and not r1b_fail and not intra_ca_conflict and not intra_dist_conflict

        result = {
            "item_id": item_id,
            "lemma": lemma,
            "bin_name": bin_name,
            "chosen_ca": chosen_ca,
            "final_distractors": final_distractors,
            "dup_fail": dup_fail,
            "r1a_fail": r1a_fail,
            "r1b_fail": r1b_fail,
            "r1b_hits": r1b_hits,
            "intra_ca_conflict": intra_ca_conflict,
            "intra_dist_conflicts": intra_dist_conflict,
            "passes": passes,
        }
        item_results.append(result)

        if not dup_fail:
            tranche_cas.add(chosen_ca)
            tranche_distractors.update(final_distractors)

    conn.close()

    pass_count = sum(1 for r in item_results if r["passes"])
    fail_count = len(item_results) - pass_count

    # Build manifest for items that pass
    manifest_items = []
    for r in item_results:
        if r["passes"]:
            manifest_items.append({
                "item_id": r["item_id"],
                "lemma": r["lemma"],
                "bin_name": r["bin_name"],
                "chosen_ca": r["chosen_ca"],
                "final_distractors": r["final_distractors"],
            })

    # Write collision report
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    collision_path = os.path.join(OUTPUT_DIR, "verb_tranche1_post_remediation_collision_report.json")
    with open(collision_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(item_results),
            "pass": pass_count,
            "fail": fail_count,
            "items": item_results,
        }, f, indent=2, ensure_ascii=False)

    # Write manifest
    manifest_path = os.path.join(OUTPUT_DIR, "verb_tranche1_post_remediation_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "tranche": "verb_tranche1",
            "total_selected": len(manifest_items),
            "bin_distribution": {
                b: sum(1 for m in manifest_items if m["bin_name"] == b)
                for b in sorted({m["bin_name"] for m in manifest_items})
            },
            "items": manifest_items,
        }, f, indent=2, ensure_ascii=False)

    # Console output
    print("=" * 60)
    print("STAGE 3 — POST-REMEDIATION COLLISION CHECK")
    print("=" * 60)
    for r in item_results:
        status = "PASS" if r["passes"] else "FAIL"
        flags = []
        if r["dup_fail"]:
            flags.append("DUP")
        if r["r1a_fail"]:
            flags.append(f"R1a(CA={r['chosen_ca']})")
        if r["r1b_fail"]:
            flags.append(f"R1b_hits={r['r1b_hits']}")
        if r["intra_ca_conflict"]:
            flags.append("INTRA_CA")
        if r["intra_dist_conflicts"]:
            flags.append(f"INTRA_DIST={r['intra_dist_conflicts']}")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        print(f"  {status:<6} id={r['item_id']:<6} bin={r['bin_name']:<5} lemma={r['lemma']}{flag_str}")

    print()
    print(f"PASS: {pass_count}/{len(item_results)}")
    print(f"FAIL: {fail_count}/{len(item_results)}")
    print()
    print("Artifacts:")
    print(f"  {collision_path}")
    print(f"  {manifest_path}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
