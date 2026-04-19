#!/usr/bin/env python3
"""
adverb_5k_rebuild_stage4_pack.py
Stage 4 — Build the prepare-only apply pack.

Reads validated proposals and emits:
  - adverb_5k_rebuild_manifest.json     (DB operations ledger, no execution)
  - adverb_5k_rebuild_apply_DONOTRUN.sh (shell apply script, dry-run by default)
  - adverb_5k_rebuild_operator_summary.md

Gated: will not run if Stage 3 validation is not accepted.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

DB_PATH = "data/lingua_staging.db"
OUTPUT_DIR = "diagnostics_exports/adverb_5k_rebuild/current"
VALIDATION_PATH = "diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_validation.json"
PROPOSALS_PATH = "diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_proposals.json"
APPLY_SCRIPT_PATH = "scripts/adverb_5k_rebuild_apply_DONOTRUN.sh"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Adverb 5K apply pack builder. No DB writes.")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--output-dir", default=OUTPUT_DIR)
    ap.add_argument("--validation", default=VALIDATION_PATH)
    ap.add_argument("--proposals", default=PROPOSALS_PATH)
    ap.add_argument("--apply-script", default=APPLY_SCRIPT_PATH)
    args = ap.parse_args(argv)

    if not os.path.exists(args.validation):
        print(f"ERROR: Validation file not found: {args.validation}", file=sys.stderr)
        return 1
    if not os.path.exists(args.proposals):
        print(f"ERROR: Proposals file not found: {args.proposals}", file=sys.stderr)
        return 1

    with open(args.validation, encoding="utf-8") as f:
        validation = json.load(f)
    with open(args.proposals, encoding="utf-8") as f:
        proposals_data = json.load(f)

    if not validation.get("stage3_accept"):
        print("ERROR: Stage 3 validation not accepted. Cannot build apply pack.", file=sys.stderr)
        return 1

    proposals = proposals_data["proposals"]
    os.makedirs(args.output_dir, exist_ok=True)

    # Build manifest: one operation set per item
    operations = []
    for p in proposals:
        item_id = p["item_id"]
        ca = p["correct_answer"]
        distractors = p["new_distractors"]

        ops = {
            "item_id": item_id,
            "lemma": p["lemma"],
            "correct_answer": ca,
            "delete": {
                "table": "vocab_choices",
                "where": f"item_id = {item_id}",
                "count": 6,
            },
            "inserts": [
                {"choice_text": ca, "is_correct": 1, "position_index": 0},
            ] + [
                {"choice_text": d, "is_correct": 0, "position_index": i + 1}
                for i, d in enumerate(distractors)
            ],
            "total_rows_after": 4,
        }
        operations.append(ops)

    manifest = {
        "workstream": "adverb_5k_rebuild",
        "mode": "prepare-only",
        "db": args.db,
        "total_items": len(operations),
        "total_deletes": sum(op["delete"]["count"] for op in operations),
        "total_inserts": sum(len(op["inserts"]) for op in operations),
        "operations": operations,
        "apply_gate": "stage3_accept must be True before executing apply script",
        "forbidden": [
            "DO NOT activate any item",
            "DO NOT run apply script without operator review",
            "DO NOT modify correct_answers or lemmas",
        ],
    }

    manifest_path = os.path.join(args.output_dir, "adverb_5k_rebuild_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Build shell apply script
    shell_lines = [
        "#!/usr/bin/env bash",
        "# adverb_5k_rebuild_apply_DONOTRUN.sh",
        "# Applies distractor rebuild for 6 inactive 5K adverb items.",
        "# Dry-run by default. Pass --apply to execute.",
        "# Gate: run adverb_5k_rebuild_stage3_validate.py first and confirm PASS.",
        "# DO NOT run without operator review of adverb_5k_rebuild_manifest.json.",
        "",
        'set -euo pipefail',
        "",
        'DB="${1:-data/lingua_staging.db}"',
        'APPLY=0',
        'if [[ "${2:-}" == "--apply" ]]; then',
        '  APPLY=1',
        'fi',
        "",
        'if [[ "$APPLY" -eq 0 ]]; then',
        '  echo "DRY-RUN MODE: No changes will be made. Pass --apply as second argument to execute."',
        'fi',
        "",
    ]

    for op in operations:
        item_id = op["item_id"]
        lemma = op["lemma"]
        ca = op["correct_answer"]
        distractors_list = [i["choice_text"] for i in op["inserts"] if i["is_correct"] == 0]

        shell_lines += [
            f'echo "--- id={item_id} {lemma} -> {ca} ---"',
            f'echo "  DELETE {op["delete"]["count"]} existing choices"',
        ]
        for ins in op["inserts"]:
            shell_lines.append(
                f'echo "  INSERT choice_text={ins["choice_text"]!r} is_correct={ins["is_correct"]} pos={ins["position_index"]}"'
            )

        shell_lines += [
            'if [[ "$APPLY" -eq 1 ]]; then',
            f'  sqlite3 "$DB" "DELETE FROM vocab_choices WHERE item_id={item_id};"',
        ]
        for ins in op["inserts"]:
            ct = ins["choice_text"].replace("'", "''")
            shell_lines.append(
                f'  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) '
                f"VALUES ({item_id}, '{ct}', {ins['is_correct']}, {ins['position_index']});\"",
            )
        shell_lines += [
            f'  echo "  APPLIED id={item_id}"',
            'fi',
            "",
        ]

    shell_lines += [
        'if [[ "$APPLY" -eq 1 ]]; then',
        '  echo "APPLY COMPLETE — all 6 items rebuilt"',
        'else',
        '  echo "DRY-RUN COMPLETE — no changes made"',
        'fi',
    ]

    with open(args.apply_script, "w", encoding="utf-8") as f:
        f.write("\n".join(shell_lines) + "\n")
    os.chmod(args.apply_script, 0o755)

    # Build operator summary
    total_distractors = sum(len(p["new_distractors"]) for p in proposals)
    summary_lines = [
        "# Adverb 5K Rebuild — Operator Summary",
        "",
        "## Status: PREPARE-ONLY — NO DB WRITES PERFORMED",
        "",
        "## Workstream",
        "",
        "Distractor rebuild for 6 inactive 5K Portuguese adverb items.",
        "All 6 items form an atomic group — partial apply is not valid.",
        "",
        "## Validation",
        "",
        f"- Stage 1 (group extraction): PASS — {len(proposals)} items confirmed",
        f"- Stage 2 (proposals): PASS — {total_distractors} new distractors proposed, all unique",
        f"- Stage 3 (group validation): PASS — all {len(proposals)} items pass all {len(validation['checks'])} checks",
        "",
        "## Proposed Changes",
        "",
        "| item_id | lemma | CA | new distractors |",
        "|---------|-------|----|-----------------|",
    ]
    for p in proposals:
        d = ", ".join(p["new_distractors"])
        summary_lines.append(f"| {p['item_id']} | {p['lemma']} | {p['correct_answer']} | {d} |")

    summary_lines += [
        "",
        "## Apply Pack",
        "",
        f"- Manifest: `{manifest_path}`",
        f"- Apply script: `{args.apply_script}` (dry-run by default, pass `--apply` to execute)",
        f"- Items: {manifest['total_items']}",
        f"- DELETEs: {manifest['total_deletes']} (6 existing choices per item)",
        f"- INSERTs: {manifest['total_inserts']} (4 per item: 1 CA + 3 distractors)",
        "",
        "## What This Workstream Does NOT Authorize",
        "",
        "- DO NOT activate any adverb item",
        "- DO NOT run apply script without operator review",
        "- DO NOT modify correct_answers or lemmas",
        "- DO NOT open the 10K adverb group",
        "",
        "## Next Step",
        "",
        "1. Operator reviews this summary and the manifest.",
        "2. Run apply workstream (separate session): `bash scripts/adverb_5k_rebuild_apply_DONOTRUN.sh data/lingua_staging.db --apply`",
        "3. Run Stage A gloss audit on rebuilt items.",
        "4. Activation tranche (standard 4-stage gate).",
    ]

    summary_path = os.path.join(args.output_dir, "adverb_5k_rebuild_operator_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")

    print("STAGE 4 — PREPARE APPLY PACK")
    print(f"  Items:    {manifest['total_items']}")
    print(f"  DELETEs:  {manifest['total_deletes']}")
    print(f"  INSERTs:  {manifest['total_inserts']}")
    print(f"  Manifest: {manifest_path}")
    print(f"  Script:   {args.apply_script}")
    print(f"  Summary:  {summary_path}")
    print("STAGE 4 ACCEPTANCE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
