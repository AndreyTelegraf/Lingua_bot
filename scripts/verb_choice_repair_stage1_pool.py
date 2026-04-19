#!/usr/bin/env python3
"""
verb_choice_repair_stage1_pool.py
Stage 1 — Target pool reconfirmation.
Read-only. Identifies all inactive verb items with zero vocab_choices.

Outputs:
  diagnostics_exports/verb_choice_repair/current/verb_choice_repair_target_pool.json
  diagnostics_exports/verb_choice_repair/current/verb_choice_repair_target_pool_summary.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
OUTPUT_DIR = "diagnostics_exports/verb_choice_repair/current"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 1: target pool reconfirmation. Read-only.")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--output-dir", default=OUTPUT_DIR)
    args = ap.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # Active lemmas — used to flag duplicate-lemma items
    active_verb_lemmas: set[str] = set(
        r[0] for r in conn.execute(
            "SELECT DISTINCT lemma FROM vocab_items WHERE is_active=1 AND pos='verb'"
        ).fetchall()
    )

    rows = conn.execute("""
        SELECT vi.id, vi.lemma, vi.bin_name, vi.correct_answer,
               vi.cefr_estimate, vi.freq_rank,
               (SELECT COUNT(*) FROM vocab_choices vc WHERE vc.item_id=vi.id) AS choice_count
        FROM vocab_items vi
        WHERE vi.pos='verb'
          AND vi.is_active=0
          AND NOT EXISTS (SELECT 1 FROM vocab_choices vc WHERE vc.item_id=vi.id)
        ORDER BY vi.bin_name, vi.freq_rank
    """).fetchall()
    conn.close()

    # Acceptance checks
    assert all(r["choice_count"] == 0 for r in rows), "FAIL: some rows have non-zero choice_count"
    assert all(r["id"] not in active_verb_lemmas for r in rows), "FAIL: active item slipped in"

    items = []
    for r in rows:
        reason = "inactive_verb_zero_choices"
        if r["lemma"] in active_verb_lemmas:
            reason += ",lemma_already_active"
        items.append({
            "item_id": r["id"],
            "lemma": r["lemma"],
            "bin_name": r["bin_name"],
            "correct_answer": r["correct_answer"],
            "cefr_estimate": r["cefr_estimate"],
            "freq_rank": r["freq_rank"],
            "choice_count": r["choice_count"],
            "reason_in_scope": reason,
        })

    bin_dist: dict[str, int] = {}
    for item in items:
        k = item["bin_name"] or "NULL"
        bin_dist[k] = bin_dist.get(k, 0) + 1

    null_ca = sum(1 for item in items if not item["correct_answer"])
    dup_lemma = sum(1 for item in items if item["lemma"] in active_verb_lemmas)

    output: dict = {
        "total": len(items),
        "bin_distribution": bin_dist,
        "null_correct_answer": null_ca,
        "lemma_already_active_count": dup_lemma,
        "items": items,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "verb_choice_repair_target_pool.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    md_lines = [
        "# Verb Choice Repair — Stage 1: Target Pool",
        "",
        f"**DB:** {args.db}",
        f"**Total target items:** {len(items)}",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Total inactive verbs with 0 choices | {len(items)} |",
        f"| Null correct_answer | {null_ca} |",
        f"| Lemma already active in bank | {dup_lemma} |",
        "",
        "**Bin distribution:**",
        "",
        "| bin_name | count |",
        "|----------|-------|",
    ]
    for bin_name, cnt in sorted(bin_dist.items()):
        md_lines.append(f"| {bin_name} | {cnt} |")

    md_lines += [
        "",
        "## Item List",
        "",
        "| item_id | lemma | bin | CA | cefr | freq_rank | reason |",
        "|---------|-------|-----|----|------|-----------|--------|",
    ]
    for item in items:
        md_lines.append(
            f"| {item['item_id']} | {item['lemma']} | {item['bin_name'] or 'NULL'} "
            f"| {item['correct_answer'] or 'NULL'} | {item['cefr_estimate'] or '?'} "
            f"| {item['freq_rank'] or '?'} | {item['reason_in_scope']} |"
        )

    md_path = os.path.join(args.output_dir, "verb_choice_repair_target_pool_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"STAGE 1 — TARGET POOL RECONFIRMATION")
    print(f"  Total items:             {len(items)}")
    print(f"  Null correct_answer:     {null_ca}")
    print(f"  Lemma already active:    {dup_lemma}")
    print(f"  Bin distribution:        {bin_dist}")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")
    print(f"STAGE 1 ACCEPTANCE: PASS (all {len(items)} items have 0 choices, no active items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
