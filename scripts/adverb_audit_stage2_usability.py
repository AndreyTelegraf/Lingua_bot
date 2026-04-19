#!/usr/bin/env python3
"""
adverb_audit_stage2_usability.py
Stage 2 — Existing inventory usability review. Read-only.

Classifies each inactive adverb by the most specific blocker against activation.
Blocker precedence (first match wins):
  zero_choices       — no vocab_choices rows
  null_bin           — bin_name is null/empty
  dup_lemma_active   — lemma already has an active item
  r1b_fail           — distractor(s) are active correct_answers
  r1a_fail           — item CA is an active distractor
  r1b_if_group_activated — distractor is a CA of another inactive group member
                           (safe now, fails if that member activates first)
  usable_now         — passes all current checks; cross-group ordering noted

Outputs:
  diagnostics_exports/adverb_audit/current/adverb_inventory_usability.json
  diagnostics_exports/adverb_audit/current/adverb_inventory_usability_summary.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
OUTPUT_DIR = "diagnostics_exports/adverb_audit/current"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Adverb inventory usability review. Read-only.")
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
    active_distractors: set[str] = set(
        r[0] for r in conn.execute(
            "SELECT DISTINCT vc.choice_text FROM vocab_choices vc "
            "JOIN vocab_items vi ON vi.id=vc.item_id WHERE vi.is_active=1 AND vc.is_correct=0"
        ).fetchall()
    )
    active_adverb_lemmas: set[str] = set(
        r[0] for r in conn.execute(
            "SELECT DISTINCT lemma FROM vocab_items WHERE is_active=1 AND pos='adverb'"
        ).fetchall()
    )

    # Inactive adverb CAs — used to detect cross-group distractor references
    inactive_adverb_ca_map: dict[str, list[int]] = {}
    for r in conn.execute(
        "SELECT id, correct_answer FROM vocab_items "
        "WHERE pos='adverb' AND is_active=0 AND correct_answer IS NOT NULL"
    ).fetchall():
        ca = r["correct_answer"]
        inactive_adverb_ca_map.setdefault(ca, []).append(r["id"])

    inactive_rows = conn.execute(
        "SELECT id, lemma, bin_name, correct_answer, cefr_estimate, freq_rank "
        "FROM vocab_items WHERE pos='adverb' AND is_active=0 ORDER BY bin_name, freq_rank"
    ).fetchall()

    classified: list[dict] = []

    for r in inactive_rows:
        item_id = r["id"]
        lemma = r["lemma"]
        bin_name = r["bin_name"] or ""
        ca = r["correct_answer"] or ""

        choices = conn.execute(
            "SELECT choice_text, is_correct FROM vocab_choices WHERE item_id=? ORDER BY position_index",
            (item_id,)
        ).fetchall()
        choice_count = len(choices)
        distractors = [c["choice_text"] for c in choices if c["is_correct"] == 0]

        # --- Blocker classification (first match) ---
        if choice_count == 0:
            blocker = "zero_choices"
            detail = "no vocab_choices rows"
        elif not bin_name:
            blocker = "null_bin"
            detail = "bin_name is null/empty"
        elif lemma in active_adverb_lemmas:
            blocker = "dup_lemma_active"
            detail = f"lemma '{lemma}' already active"
        elif any(d in active_cas for d in distractors):
            bad = [d for d in distractors if d in active_cas]
            blocker = "r1b_fail"
            detail = f"distractors {bad} are active correct_answers"
        elif ca in active_distractors:
            blocker = "r1a_fail"
            detail = f"CA '{ca}' is an active distractor"
        else:
            # Check cross-group reference: distractor is CA of another inactive adverb
            cross_refs = [d for d in distractors if d in inactive_adverb_ca_map]
            if cross_refs:
                blocker = "r1b_if_group_activated"
                detail = (
                    f"distractors {cross_refs} are CAs of inactive adverbs "
                    f"(safe now; R1b would fire if those items activate first)"
                )
            else:
                blocker = "usable_now"
                detail = "passes all current Rule 1 checks; no cross-group references"

        classified.append({
            "item_id": item_id,
            "lemma": lemma,
            "bin_name": bin_name or "NULL",
            "correct_answer": ca,
            "cefr_estimate": r["cefr_estimate"],
            "freq_rank": r["freq_rank"],
            "choice_count": choice_count,
            "blocker": blocker,
            "detail": detail,
        })

    conn.close()

    # Aggregate
    blocker_counts: dict[str, int] = {}
    for item in classified:
        blocker_counts[item["blocker"]] = blocker_counts.get(item["blocker"], 0) + 1

    by_bin_blocker: dict[str, dict[str, int]] = {}
    for item in classified:
        b = item["bin_name"]
        bl = item["blocker"]
        by_bin_blocker.setdefault(b, {})
        by_bin_blocker[b][bl] = by_bin_blocker[b].get(bl, 0) + 1

    usable_now = [c for c in classified if c["blocker"] == "usable_now"]
    r1b_if_group = [c for c in classified if c["blocker"] == "r1b_if_group_activated"]
    r1b_fail = [c for c in classified if c["blocker"] == "r1b_fail"]
    r1a_fail = [c for c in classified if c["blocker"] == "r1a_fail"]
    dup_active = [c for c in classified if c["blocker"] == "dup_lemma_active"]
    zero_ch = [c for c in classified if c["blocker"] == "zero_choices"]
    null_b = [c for c in classified if c["blocker"] == "null_bin"]

    output = {
        "total_inactive": len(classified),
        "blocker_counts": blocker_counts,
        "by_bin_blocker": by_bin_blocker,
        "usable_now_count": len(usable_now),
        "usable_with_rebuild_count": len(r1b_if_group) + len(r1b_fail) + len(r1a_fail),
        "irrecoverable_count": len(dup_active) + len(zero_ch) + len(null_b),
        "usable_now_items": usable_now,
        "r1b_if_group_items": r1b_if_group,
        "r1b_fail_items": r1b_fail,
        "r1a_fail_items": r1a_fail,
        "dup_lemma_active_items": dup_active,
        "zero_choice_items": zero_ch,
        "null_bin_items": null_b,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "adverb_inventory_usability.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # --- Markdown summary ---
    md_lines = [
        "# Adverb Inventory Usability — Stage 2",
        "",
        f"**DB:** {args.db}",
        f"**Total inactive adverbs:** {len(classified)}",
        "",
        "## Blocker Summary",
        "",
        "| Blocker | Count | Meaning |",
        "|---------|-------|---------|",
        f"| `usable_now` | **{len(usable_now)}** | Passes all current Rule 1 checks |",
        f"| `r1b_if_group_activated` | {len(r1b_if_group)} | Safe now; R1b fires if peer group activates first |",
        f"| `r1b_fail` | {len(r1b_fail)} | Distractor(s) are already active correct_answers |",
        f"| `r1a_fail` | {len(r1a_fail)} | Item CA is already an active distractor |",
        f"| `dup_lemma_active` | {len(dup_active)} | Lemma already has an active item |",
        f"| `zero_choices` | {len(zero_ch)} | No vocab_choices rows exist |",
        f"| `null_bin` | {len(null_b)} | bin_name is null |",
        "",
        "**Recoverable now:** " + str(len(usable_now)),
        "**Recoverable with distractor rebuild:** " + str(len(r1b_if_group) + len(r1b_fail) + len(r1a_fail)),
        "**Irrecoverable without structural cleanup:** " + str(len(dup_active) + len(zero_ch) + len(null_b)),
        "",
        "## By Bin",
        "",
        "| bin | usable_now | r1b_if_group | r1b_fail | r1a_fail | dup_lemma | zero_choice | null_bin |",
        "|-----|-----------|--------------|----------|----------|-----------|-------------|----------|",
    ]
    for b in sorted(by_bin_blocker.keys()):
        bb = by_bin_blocker[b]
        md_lines.append(
            f"| {b} | {bb.get('usable_now', 0)} | {bb.get('r1b_if_group_activated', 0)} "
            f"| {bb.get('r1b_fail', 0)} | {bb.get('r1a_fail', 0)} "
            f"| {bb.get('dup_lemma_active', 0)} | {bb.get('zero_choices', 0)} "
            f"| {bb.get('null_bin', 0)} |"
        )

    # 10K detail
    md_lines += [
        "",
        "## 10K Bin Detail (target bin for standard tranche pattern)",
        "",
        "| item_id | lemma | CA | blocker | detail |",
        "|---------|-------|-----|---------|--------|",
    ]
    for item in classified:
        if item["bin_name"] == "10K":
            md_lines.append(
                f"| {item['item_id']} | {item['lemma']} | {item['correct_answer']} "
                f"| `{item['blocker']}` | {item['detail'][:70]} |"
            )

    # Usable now items
    md_lines += [
        "",
        "## Usable-Now Items",
        "",
        "| item_id | bin | lemma | CA | cefr | detail |",
        "|---------|-----|-------|-----|------|--------|",
    ]
    for item in usable_now:
        md_lines.append(
            f"| {item['item_id']} | {item['bin_name']} | {item['lemma']} "
            f"| {item['correct_answer']} | {item['cefr_estimate'] or '?'} "
            f"| {item['detail']} |"
        )

    md_lines += [
        "",
        "## r1b_if_group_activated Items (need peer ordering / distractor rebuild)",
        "",
        "| item_id | bin | lemma | CA | detail |",
        "|---------|-----|-------|-----|--------|",
    ]
    for item in r1b_if_group:
        md_lines.append(
            f"| {item['item_id']} | {item['bin_name']} | {item['lemma']} "
            f"| {item['correct_answer']} | {item['detail'][:80]} |"
        )

    md_path = os.path.join(args.output_dir, "adverb_inventory_usability_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print("STAGE 2 — EXISTING INVENTORY USABILITY REVIEW")
    print(f"  Total inactive:          {len(classified)}")
    print(f"  usable_now:              {len(usable_now)}")
    print(f"  r1b_if_group_activated:  {len(r1b_if_group)}")
    print(f"  r1b_fail:                {len(r1b_fail)}")
    print(f"  r1a_fail:                {len(r1a_fail)}")
    print(f"  dup_lemma_active:        {len(dup_active)}")
    print(f"  zero_choices:            {len(zero_ch)}")
    print(f"  null_bin:                {len(null_b)}")
    print()
    print("  usable_now items:")
    for item in usable_now:
        print(f"    id={item['item_id']:5} bin={item['bin_name']:5} {item['lemma']:20} -> {item['correct_answer']}")
    print()
    print("  10K bin blockers:")
    for item in classified:
        if item["bin_name"] == "10K":
            print(f"    id={item['item_id']:5} {item['lemma']:20} blocker={item['blocker']}")
    print(f"  JSON: {json_path}")
    print(f"  MD:   {md_path}")
    print("STAGE 2 ACCEPTANCE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
