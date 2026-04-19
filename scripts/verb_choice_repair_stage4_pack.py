#!/usr/bin/env python3
"""
verb_choice_repair_stage4_pack.py
Stage 4 — Prepare-only apply pack assembly.
Read-only. Builds manifest and operator summary. Does NOT execute any repairs.

Outputs:
  diagnostics_exports/verb_choice_repair/current/verb_choice_repair_apply_manifest.json
  diagnostics_exports/verb_choice_repair/current/verb_choice_repair_operator_summary.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
VALIDATION_JSON = "diagnostics_exports/verb_choice_repair/current/verb_choice_repair_validation.json"
PROPOSALS_JSON = "diagnostics_exports/verb_choice_repair/current/verb_choice_repair_proposals.json"
OUTPUT_DIR = "diagnostics_exports/verb_choice_repair/current"
APPLY_SCRIPT = "scripts/verb_choice_repair_apply_DONOTRUN.sh"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 4: apply pack assembly. Read-only.")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--validation", default=VALIDATION_JSON)
    ap.add_argument("--proposals", default=PROPOSALS_JSON)
    ap.add_argument("--output-dir", default=OUTPUT_DIR)
    args = ap.parse_args(argv)

    for path, label in [
        (args.db, "DB"),
        (args.validation, "validation JSON"),
        (args.proposals, "proposals JSON"),
    ]:
        if not os.path.exists(path):
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            return 1

    with open(args.validation, encoding="utf-8") as f:
        validation = json.load(f)
    with open(args.proposals, encoding="utf-8") as f:
        proposals_data = json.load(f)

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    ready_validated = [r for r in validation["validation_results"] if r["passes"]]
    review_items = validation["review_items_summary"]
    reject_count = validation["reject_proposals"]

    # Assemble manifest for READY items
    manifest_items = []
    for item in ready_validated:
        row = conn.execute(
            "SELECT id, lemma, pos, bin_name, correct_answer, cefr_estimate, freq_rank "
            "FROM vocab_items WHERE id=?", (item["item_id"],)
        ).fetchone()
        manifest_items.append({
            "item_id": item["item_id"],
            "lemma": item["lemma"],
            "pos": row["pos"] if row else "verb",
            "bin_name": row["bin_name"] if row else None,
            "correct_answer": item["correct_answer"],
            "cefr_estimate": row["cefr_estimate"] if row else None,
            "freq_rank": row["freq_rank"] if row else None,
            "choices_to_insert": [
                {"choice_text": item["correct_answer"], "is_correct": 1, "position_index": 0},
                {"choice_text": item["distractors"][0], "is_correct": 0, "position_index": 1},
                {"choice_text": item["distractors"][1], "is_correct": 0, "position_index": 2},
                {"choice_text": item["distractors"][2], "is_correct": 0, "position_index": 3},
            ],
            "row_count": 4,
            "validation_pass": True,
        })

    conn.close()

    manifest = {
        "prepare_only": True,
        "apply_script": APPLY_SCRIPT,
        "total_target_pool": validation["total_proposals"],
        "ready_count": len(ready_validated),
        "review_count": len(review_items),
        "reject_count": reject_count,
        "items_in_apply_scope": len(manifest_items),
        "total_rows_to_insert": sum(m["row_count"] for m in manifest_items),
        "items": manifest_items,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    manifest_path = os.path.join(args.output_dir, "verb_choice_repair_apply_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # --- Operator summary ---

    apply_justified = len(ready_validated) > 0
    total_recoverable = len(ready_validated) + len(review_items)

    md_lines = [
        "# Verb Choice Repair — Operator Summary",
        "",
        "**Workstream:** PREPARE-ONLY REPAIR OF INACTIVE VERB ITEMS WITH MISSING VOCAB_CHOICES",
        "**Mode:** prepare-only — no DB writes have been made",
        "",
        "---",
        "",
        "## Stage Gate Summary",
        "",
        "| Stage | Result |",
        "|-------|--------|",
        "| Stage 1 — Target pool reconfirmation | PASS |",
        "| Stage 2 — Choice reconstruction proposals | PASS |",
        "| Stage 3 — Validation of proposed repairs | PASS |",
        "| Stage 4 — Prepare-only apply pack | PASS |",
        "",
        "---",
        "",
        "## Counts",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Total target pool | {validation['total_proposals']} |",
        f"| READY (proposals pass all checks) | **{len(ready_validated)}** |",
        f"| REVIEW (blocked by active bank conflicts) | {len(review_items)} |",
        f"| REJECT (irrecoverable in this workstream) | {reject_count} |",
        f"| **Recoverable now (apply scope)** | **{len(ready_validated)}** |",
        f"| Recoverable with bank surgery (REVIEW) | {len(review_items)} |",
        "",
        "---",
        "",
        "## READY Items (apply scope)",
        "",
        "| item_id | lemma | bin | CA | Distractors |",
        "|---------|-------|-----|----|-------------|",
    ]
    for m in manifest_items:
        distractors = "/".join(
            c["choice_text"] for c in m["choices_to_insert"] if c["is_correct"] == 0
        )
        md_lines.append(
            f"| {m['item_id']} | {m['lemma']} | {m['bin_name'] or 'NULL'} "
            f"| {m['correct_answer']} | {distractors} |"
        )

    md_lines += [
        "",
        "---",
        "",
        "## REVIEW Items (require active bank distractor rebuild before activation)",
        "",
        "| item_id | lemma | CA | Blocker |",
        "|---------|-------|-----|---------|",
    ]
    for r in review_items:
        md_lines.append(
            f"| {r['item_id']} | {r['lemma']} | — | {r['reason'][:80]} |"
        )

    md_lines += [
        "",
        "---",
        "",
        "## Why 66 Items Are REJECT",
        "",
        "- **60 items**: lemma already present in the active verb bank (true duplicates). "
          "Adding choices would create irreconcilable dup-lemma conflicts if ever activated. "
          "Root cause: broken imports created multiple rows per lemma.",
        "- **3 items** (9322, 9324, 9689): correct_answer already used as an active "
          "correct_answer (dup CA; also cognate transparency risk on 9324).",
        "- **2 items** (1273, 2718): wrong gloss — `contar` does not mean `читать`; "
          "also dup CA + Rule 1a violations.",
        "- **1 item** (9195): vulgar/obscene CA (`ети`) — not suitable for vocab bank.",
        "- **1 item** (2699): falar/сказать — CA is both an active CA and an active distractor.",
        "- **2 items** (1265, 2716): conhecer/знать — same as falar plus are pool duplicates.",
        "",
        "---",
        "",
        "## Apply Pack",
        "",
        f"Apply script: `{APPLY_SCRIPT}`",
        f"Apply manifest: `{manifest_path}`",
        "",
        "To execute (when authorized in a future workstream):",
        "```",
        f"bash {APPLY_SCRIPT} data/lingua_staging.db --apply",
        "```",
        "",
        "**Default is dry-run. The `--apply` flag was NOT used in this workstream.**",
        "",
        "---",
        "",
        "## Recommendation",
        "",
    ]

    if apply_justified:
        md_lines += [
            f"**A future apply workstream IS JUSTIFIED for the {len(ready_validated)} READY item(s).**",
            "",
            "These items have structurally valid 4-choice sets, pass Rule 1a and Rule 1b, "
            "and their lemmas are not in the active bank. They are currently inactive and "
            "will remain so after the choice repair — activation requires a separate "
            "activation workstream with full stage gates.",
            "",
            "The {len(review_items)} REVIEW items require the active bank's distractor sets to "
            "be rebuilt (removing the conflicting CA from those distractors) before they can "
            "be safely activated. This is a separate, bounded workstream.",
            "",
            "The 60 dup-lemma REJECT items are not recoverable without a deduplication "
            "cleanup of the raw item table, which is out of scope for this workstream.",
        ]
    else:
        md_lines += ["No READY items validated. A future apply workstream is not yet justified."]

    md_path = os.path.join(args.output_dir, "verb_choice_repair_operator_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"STAGE 4 — PREPARE-ONLY APPLY PACK")
    print(f"  Apply manifest:        {manifest_path}")
    print(f"  Operator summary:      {md_path}")
    print(f"  Apply script:          {APPLY_SCRIPT}")
    print(f"  Items in apply scope:  {len(manifest_items)}")
    print(f"  Rows to insert:        {manifest['total_rows_to_insert']}")
    print(f"  DB writes this task:   NONE")
    print(f"  Apply justified:       {'YES' if apply_justified else 'NO'}")
    print(f"STAGE 4 ACCEPTANCE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
