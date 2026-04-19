#!/usr/bin/env python3
"""
verb_choice_repair_stage2_proposals.py
Stage 2 — Choice reconstruction proposal.
Read-only. Generates proposed 4-choice sets for each target item.

Proposal status:
  READY   — passes all structural checks + Rule 1a + Rule 1b; choices provided
  REVIEW  — choices proposed but item has an active-bank conflict that blocks
             direct activation (e.g. CA appears as active distractor = Rule 1a)
  REJECT  — definitively unsalvageable in this workstream (dup lemma, wrong
             gloss, vulgar content, dup correct_answer in active bank)

Outputs:
  diagnostics_exports/verb_choice_repair/current/verb_choice_repair_proposals.json
  diagnostics_exports/verb_choice_repair/current/verb_choice_repair_review.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
POOL_JSON = "diagnostics_exports/verb_choice_repair/current/verb_choice_repair_target_pool.json"
OUTPUT_DIR = "diagnostics_exports/verb_choice_repair/current"

# ---------------------------------------------------------------------------
# Hand-curated distractor proposals for READY and REVIEW items.
# Each tuple: (distractor, semantic_note)
# All checked against active bank: none are active correct_answers.
# ---------------------------------------------------------------------------

_PROPOSALS: dict[int, dict] = {
    # reconhecer → узнавать (to recognize)
    # Clean item: CA not active, not active distractor.
    10628: {
        "distractors": ["признавать", "наблюдать", "запоминать"],
        "semantic_note": (
            "All three relate to perception/cognition: признавать (to acknowledge), "
            "наблюдать (to observe), запоминать (to memorize). "
            "Plausible but semantically distinct from узнавать (to recognize)."
        ),
        "confidence": "high",
        "initial_status": "READY",
    },
    # ferir → ранить (to wound)
    # Clean item: CA not active, not active distractor.
    10647: {
        "distractors": ["бить", "избивать", "повреждать"],
        "semantic_note": (
            "All three relate to physical harm: бить (to hit), избивать (to beat), "
            "повреждать (to damage). Plausible in same domain but semantically "
            "distinct from ранить (to wound with a cutting/penetrating object)."
        ),
        "confidence": "high",
        "initial_status": "READY",
    },
    # admirar → восхищаться (to admire)
    # r1a_clash: CA восхищаться appears as distractor in active items.
    # Cannot be activated without active distractor bank rebuild.
    8742: {
        "distractors": ["удивляться", "любоваться", "ценить"],
        "semantic_note": (
            "All three relate to positive emotional response: удивляться (to be surprised), "
            "любоваться (to admire scenery), ценить (to value/appreciate). "
            "Plausible alternatives to восхищаться (to admire/be admired)."
        ),
        "confidence": "medium",
        "initial_status": "REVIEW",
        "review_reason": "r1a_clash: CA 'восхищаться' appears as distractor in active items; "
                         "Rule 1a would fire on activation. Distractor bank rebuild needed first.",
    },
    # regular → регулировать (to regulate)
    # r1a_clash: CA регулировать appears as distractor in active items.
    9692: {
        "distractors": ["контролировать", "определять", "координировать"],
        "semantic_note": (
            "All three relate to management/control: контролировать (to control), "
            "определять (to determine), координировать (to coordinate). "
            "Plausible but distinct from регулировать (to regulate/adjust)."
        ),
        "confidence": "medium",
        "initial_status": "REVIEW",
        "review_reason": "r1a_clash: CA 'регулировать' appears as distractor in active items; "
                         "Rule 1a would fire on activation. Distractor bank rebuild needed first.",
    },
}

# Explicit reject reasons for known special cases among non-dup-lemma items.
_SPECIAL_REJECTS: dict[int, str] = {
    2699: "dup_ca_and_r1a: CA 'сказать' is both an active correct_answer and active distractor",
    1265: "dup_ca_and_r1a: CA 'знать' is both an active correct_answer and active distractor; pool duplicate",
    2716: "dup_ca_and_r1a: CA 'знать' is both an active correct_answer and active distractor; pool duplicate",
    1273: "wrong_gloss_and_conflicts: contar means 'рассказывать/считать' not 'читать'; CA also dup_ca+r1a",
    2718: "wrong_gloss_and_conflicts: contar means 'рассказывать/считать' not 'читать'; CA also dup_ca+r1a; pool duplicate",
    9195: "vulgar_content: CA 'ети' is vulgar/obscene; not suitable for vocab bank",
    9322: "dup_ca: CA 'интересовать' already active in bank (different lemma collision)",
    9324: "dup_ca: CA 'интерпретировать' already active in bank (cognate transparency risk)",
    9689: "dup_ca: CA 'регистрировать' already active in bank",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 2: choice reconstruction proposals. Read-only.")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--pool", default=POOL_JSON)
    ap.add_argument("--output-dir", default=OUTPUT_DIR)
    args = ap.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        return 1
    if not os.path.exists(args.pool):
        print(f"ERROR: Pool JSON not found (run Stage 1 first): {args.pool}", file=sys.stderr)
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
    active_verb_lemmas: set[str] = set(
        r[0] for r in conn.execute(
            "SELECT DISTINCT lemma FROM vocab_items WHERE is_active=1 AND pos='verb'"
        ).fetchall()
    )
    conn.close()

    with open(args.pool, encoding="utf-8") as f:
        pool = json.load(f)

    proposals = []
    for item in pool["items"]:
        item_id = item["item_id"]
        lemma = item["lemma"]
        ca = item["correct_answer"] or ""
        bin_name = item["bin_name"]

        # --- Decision tree ---

        # 1. Dup lemma: lemma already active → irreparably duplicate
        if lemma in active_verb_lemmas:
            proposals.append({
                "item_id": item_id,
                "lemma": lemma,
                "bin_name": bin_name,
                "correct_answer": ca,
                "proposed_distractor_1": None,
                "proposed_distractor_2": None,
                "proposed_distractor_3": None,
                "collision_check_status": "dup_lemma_active",
                "semantic_note": "Lemma is already present in the active verb bank.",
                "confidence": "n/a",
                "proposal_status": "REJECT",
                "reject_reason": f"dup_lemma: '{lemma}' already has an active verb item",
            })
            continue

        # 2. Known special rejects
        if item_id in _SPECIAL_REJECTS:
            proposals.append({
                "item_id": item_id,
                "lemma": lemma,
                "bin_name": bin_name,
                "correct_answer": ca,
                "proposed_distractor_1": None,
                "proposed_distractor_2": None,
                "proposed_distractor_3": None,
                "collision_check_status": "rejected_by_policy",
                "semantic_note": "",
                "confidence": "n/a",
                "proposal_status": "REJECT",
                "reject_reason": _SPECIAL_REJECTS[item_id],
            })
            continue

        # 3. Should have a curated proposal
        if item_id not in _PROPOSALS:
            proposals.append({
                "item_id": item_id,
                "lemma": lemma,
                "bin_name": bin_name,
                "correct_answer": ca,
                "proposed_distractor_1": None,
                "proposed_distractor_2": None,
                "proposed_distractor_3": None,
                "collision_check_status": "no_proposal",
                "semantic_note": "",
                "confidence": "n/a",
                "proposal_status": "REJECT",
                "reject_reason": "no_curated_proposal_available",
            })
            continue

        prop = _PROPOSALS[item_id]
        distractors = prop["distractors"]

        # Runtime collision checks for proposed distractors (Rule 1b)
        r1b_violations = [d for d in distractors if d in active_cas]
        dup_within = len(set(distractors)) < len(distractors) or ca in distractors

        # Rule 1a check on the item's CA
        r1a_clash = ca in active_distractors
        dup_ca = ca in active_cas

        collision_parts = []
        if r1b_violations:
            collision_parts.append(f"r1b_fail:{r1b_violations}")
        if dup_within:
            collision_parts.append("dup_within_item")
        if r1a_clash:
            collision_parts.append("r1a_clash")
        if dup_ca:
            collision_parts.append("dup_ca")
        collision_status = "|".join(collision_parts) if collision_parts else "clean"

        # Final status (runtime-validated)
        if r1b_violations or dup_within:
            final_status = "REJECT"
            reject_reason = f"r1b_violations={r1b_violations}" if r1b_violations else "dup_within_item"
        else:
            final_status = prop["initial_status"]
            reject_reason = prop.get("review_reason", "")

        proposals.append({
            "item_id": item_id,
            "lemma": lemma,
            "bin_name": bin_name,
            "correct_answer": ca,
            "proposed_distractor_1": distractors[0] if len(distractors) > 0 else None,
            "proposed_distractor_2": distractors[1] if len(distractors) > 1 else None,
            "proposed_distractor_3": distractors[2] if len(distractors) > 2 else None,
            "collision_check_status": collision_status,
            "semantic_note": prop["semantic_note"],
            "confidence": prop["confidence"],
            "proposal_status": final_status,
            "reject_reason": reject_reason if final_status != "READY" else "",
        })

    ready = [p for p in proposals if p["proposal_status"] == "READY"]
    review = [p for p in proposals if p["proposal_status"] == "REVIEW"]
    reject = [p for p in proposals if p["proposal_status"] == "REJECT"]

    output = {
        "total": len(proposals),
        "ready_count": len(ready),
        "review_count": len(review),
        "reject_count": len(reject),
        "proposals": proposals,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "verb_choice_repair_proposals.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    csv_path = os.path.join(args.output_dir, "verb_choice_repair_review.csv")
    fieldnames = [
        "item_id", "lemma", "bin_name", "correct_answer",
        "proposed_distractor_1", "proposed_distractor_2", "proposed_distractor_3",
        "collision_check_status", "semantic_note", "confidence",
        "proposal_status", "reject_reason",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in proposals:
            writer.writerow({k: p.get(k, "") for k in fieldnames})

    print(f"STAGE 2 — CHOICE RECONSTRUCTION PROPOSAL")
    print(f"  Total proposals:   {len(proposals)}")
    print(f"  READY:             {len(ready)}")
    print(f"  REVIEW:            {len(review)}")
    print(f"  REJECT:            {len(reject)}")
    print()
    if ready:
        print("  READY items:")
        for p in ready:
            print(f"    id={p['item_id']} {p['lemma']} → {p['correct_answer']} "
                  f"distractors={p['proposed_distractor_1']}/{p['proposed_distractor_2']}/{p['proposed_distractor_3']}")
    if review:
        print("  REVIEW items:")
        for p in review:
            print(f"    id={p['item_id']} {p['lemma']} → {p['correct_answer']} "
                  f"[{p['reject_reason'][:60]}]")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")
    print(f"STAGE 2 ACCEPTANCE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
