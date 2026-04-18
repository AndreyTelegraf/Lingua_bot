#!/usr/bin/env python3
"""
verb_tranche1_remediation_extract.py

STAGE 1 — Read-only. Extract exact collision detail for each of the
9 non-duplicate 10K READY target items.

Outputs:
  verb_tranche1_remediation_targets.json
  verb_tranche1_remediation_targets_summary.md
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
COLLISION_REPORT = "diagnostics_exports/verb_tranche1/current/verb_tranche1_collision_report.json"
OUTPUT_DIR = "diagnostics_exports/verb_tranche1/current"

TARGET_LEMMAS = {
    "acelerar", "alterar", "implementar", "instalar",
    "pintar", "aproximar", "cancelar", "curtir", "inventar",
}


def main() -> int:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    with open(COLLISION_REPORT) as f:
        report = json.load(f)

    # Build active bank sets
    active_cas: dict[str, int] = {}
    for row in conn.execute(
        "SELECT id, correct_answer FROM vocab_items WHERE is_active=1 AND correct_answer IS NOT NULL"
    ).fetchall():
        ca = (row["correct_answer"] or "").strip()
        if ca:
            active_cas[ca] = row["id"]

    active_distractors: dict[str, list[int]] = {}
    for row in conn.execute(
        "SELECT vc.item_id, vc.choice_text FROM vocab_choices vc "
        "JOIN vocab_items vi ON vi.id=vc.item_id WHERE vi.is_active=1 AND vc.is_correct=0"
    ).fetchall():
        text = (row["choice_text"] or "").strip()
        if text:
            active_distractors.setdefault(text, []).append(row["item_id"])

    # Find target items from full_collision_results
    target_items = []
    for cr in report["full_collision_results"]:
        if cr["lemma"] in TARGET_LEMMAS:
            target_items.append(cr)

    # Enrich: get actual distractor choice rows from DB
    results = []
    for item in target_items:
        item_id = item["item_id"]
        choices = conn.execute(
            "SELECT id, choice_text, is_correct FROM vocab_choices WHERE item_id=? ORDER BY id",
            (item_id,),
        ).fetchall()

        distractor_detail = []
        for ch in choices:
            if ch["is_correct"]:
                continue
            text = (ch["choice_text"] or "").strip()
            r1b_conflict = text in active_cas
            distractor_detail.append({
                "choice_id": ch["id"],
                "choice_text": text,
                "r1b_conflict": r1b_conflict,
                "r1b_conflict_with_item": active_cas.get(text),
            })

        ca = (item["correct_answer"] or "").strip()
        r1a_conflict_items = active_distractors.get(ca, [])

        conflict_slots = [d for d in distractor_detail if d["r1b_conflict"]]

        results.append({
            "item_id": item_id,
            "lemma": item["lemma"],
            "bin_name": item["bin_name"],
            "correct_answer": ca,
            "r1a_conflict": bool(r1a_conflict_items),
            "r1a_conflict_with_items": r1a_conflict_items,
            "all_distractors": distractor_detail,
            "conflict_slots": conflict_slots,
            "clean_slots": [d for d in distractor_detail if not d["r1b_conflict"]],
            "slots_needing_replacement": len(conflict_slots),
            "total_distractors": len(distractor_detail),
        })

    conn.close()

    # Write JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR, "verb_tranche1_remediation_targets.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Write summary MD
    lines = [
        "# Verb Tranche1 Remediation Targets — Stage 1",
        "",
        f"**Source DB:** {DB_PATH}",
        f"**Active bank size:** 809 items (808 distinct CAs)",
        "",
        "## Target Items",
        "",
        "| item_id | lemma | CA | R1a | R1b slots | total dist | slots to fix |",
        "|---------|-------|----|-----|-----------|------------|--------------|",
    ]
    total_slots = 0
    for r in results:
        lines.append(
            f"| {r['item_id']} | {r['lemma']} | {r['correct_answer']} "
            f"| {'YES' if r['r1a_conflict'] else 'no'} "
            f"| {r['slots_needing_replacement']} "
            f"| {r['total_distractors']} "
            f"| {r['slots_needing_replacement']} |"
        )
        total_slots += r["slots_needing_replacement"]
    lines += [
        "",
        f"**Total slots needing replacement: {total_slots}**",
        "",
    ]

    for r in results:
        lines += [
            f"## {r['lemma']} (id={r['item_id']}, bin={r['bin_name']})",
            "",
            f"**Correct answer:** `{r['correct_answer']}`",
        ]
        if r["r1a_conflict"]:
            lines.append(
                f"**Rule 1a FAIL:** `{r['correct_answer']}` is a distractor in active items "
                f"{r['r1a_conflict_with_items']} — the CA itself must change or those active items "
                "must drop the word from distractors. *(CA is fixed; active bank distractors "
                "cannot be changed here — the CA must be accepted as-is. Rule 1a unblocks itself "
                "once the conflicting active distractors are noted as acceptable coexistence "
                "OR the inactive item's CA is replaced. See proposal stage.)*"
            )
        lines += ["", "**Distractors:**", ""]
        for d in r["all_distractors"]:
            flag = " ← **CONFLICT** (CA of active item " + str(d["r1b_conflict_with_item"]) + ")" if d["r1b_conflict"] else ""
            lines.append(f"- `{d['choice_text']}`{flag}")
        lines.append("")

    md_path = os.path.join(OUTPUT_DIR, "verb_tranche1_remediation_targets_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Console summary
    print("=" * 60)
    print("STAGE 1 — TARGETED COLLISION EXTRACTION")
    print("=" * 60)
    for r in results:
        print(f"\n  {r['lemma']} (id={r['item_id']}, bin={r['bin_name']})")
        print(f"    CA: {r['correct_answer']}")
        print(f"    R1a conflict: {r['r1a_conflict']}")
        print(f"    Slots to fix: {r['slots_needing_replacement']} / {r['total_distractors']}")
        for d in r["conflict_slots"]:
            print(f"      CONFLICT: '{d['choice_text']}' (choice_id={d['choice_id']}) — CA of item {d['r1b_conflict_with_item']}")
    print(f"\nTotal slots needing replacement: {total_slots}")
    print(f"\nArtifacts:")
    print(f"  {json_path}")
    print(f"  {md_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
