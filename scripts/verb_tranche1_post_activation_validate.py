#!/usr/bin/env python3
"""
verb_tranche1_post_activation_validate.py
Stage 3 — Post-activation live validation. Read-only.
Outputs:
  verb_tranche1_post_activation_validation.json
  verb_tranche1_post_activation_validation.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
MANIFEST_PATH = "diagnostics_exports/verb_tranche1/current/verb_tranche1_activation_manifest.json"
OUTPUT_DIR = "diagnostics_exports/verb_tranche1/current"

TARGET_IDS = [868, 921, 1732, 1759, 2172, 3467, 3491, 3509, 9328]
EXPECTED_VERB_AFTER = 185
EXPECTED_VERB_10K_AFTER = 50
EXPECTED_TOTAL_AFTER = 818
NOUN_10K_EXPECTED = 13
ADVERB_EXPECTED = 40


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    manifest_by_id = {m["item_id"]: m for m in manifest["items"]}

    # Active bank sets (now includes newly activated items)
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

    active_lemmas: set[str] = set()
    for row in conn.execute("SELECT lemma FROM vocab_items WHERE is_active=1").fetchall():
        active_lemmas.add((row["lemma"] or "").strip())

    # Bank counts
    total_active = conn.execute("SELECT COUNT(*) FROM vocab_items WHERE is_active=1").fetchone()[0]
    verb_active = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='verb'"
    ).fetchone()[0]
    verb_10k = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='verb' AND bin_name='10K'"
    ).fetchone()[0]
    noun_10k = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='noun' AND bin_name='10K'"
    ).fetchone()[0]
    adverb_active = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='adverb'"
    ).fetchone()[0]

    global_checks: list[tuple[str, str]] = []
    issues: list[str] = []

    def chk(name: str, ok: bool, detail: str = "") -> None:
        result = "PASS" if ok else f"FAIL{': ' + detail if detail else ''}"
        global_checks.append((name, result))
        if not ok:
            issues.append(f"{name}: {detail}")

    chk("Total active = 818", total_active == EXPECTED_TOTAL_AFTER, f"got {total_active}")
    chk("Active verbs = 185", verb_active == EXPECTED_VERB_AFTER, f"got {verb_active}")
    chk("Active verb/10K = 50", verb_10k == EXPECTED_VERB_10K_AFTER, f"got {verb_10k}")
    chk("noun/10K unchanged = 13", noun_10k == NOUN_10K_EXPECTED, f"got {noun_10k}")
    chk("adverbs unchanged = 40", adverb_active == ADVERB_EXPECTED, f"got {adverb_active}")

    # Per-item validation
    item_results = []
    for item_id in TARGET_IDS:
        row = conn.execute(
            "SELECT id, lemma, pos, correct_answer, is_active, bin_name FROM vocab_items WHERE id=?",
            (item_id,)
        ).fetchone()
        if row is None:
            issues.append(f"item_id={item_id} NOT FOUND")
            item_results.append({"item_id": item_id, "error": "NOT_FOUND", "passes": False})
            continue

        ca = (row["correct_answer"] or "").strip()
        lemma = (row["lemma"] or "").strip()
        is_active = row["is_active"]
        bin_name = (row["bin_name"] or "").strip()

        item_issues: list[str] = []

        # is_active=1 confirmed
        if is_active != 1:
            item_issues.append(f"is_active={is_active} (expected 1)")

        # CA matches manifest
        manifest_ca = manifest_by_id[item_id]["correct_answer"]
        if ca != manifest_ca:
            item_issues.append(f"CA mismatch: live='{ca}' manifest='{manifest_ca}'")

        # R1a: CA still not in other active items' distractors
        # (exclude own contributions — check if CA appears as distractor in items OTHER than self)
        r1a_others = conn.execute(
            "SELECT COUNT(*) FROM vocab_choices vc "
            "JOIN vocab_items vi ON vi.id=vc.item_id "
            "WHERE vi.is_active=1 AND vc.is_correct=0 AND vc.choice_text=? AND vi.id!=?",
            (ca, item_id)
        ).fetchone()[0]
        if r1a_others > 0:
            item_issues.append(f"R1a: CA '{ca}' is distractor in {r1a_others} other active items")

        # R1b: no own distractor is CA of OTHER active items
        dist_rows = conn.execute(
            "SELECT choice_text FROM vocab_choices WHERE item_id=? AND is_correct=0", (item_id,)
        ).fetchall()
        distractor_texts = [(r["choice_text"] or "").strip() for r in dist_rows]
        r1b_hits = []
        for d in distractor_texts:
            if d and conn.execute(
                "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND correct_answer=? AND id!=?",
                (d, item_id)
            ).fetchone()[0] > 0:
                r1b_hits.append(d)
        if r1b_hits:
            item_issues.append(f"R1b: distractors match CAs of other active items: {r1b_hits}")

        # no dup lemma (only one active item with this lemma)
        dup_ct = conn.execute(
            "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND lemma=?", (lemma,)
        ).fetchone()[0]
        if dup_ct > 1:
            item_issues.append(f"dup lemma: {dup_ct} active items with lemma='{lemma}'")

        # choice integrity
        correct_ct = conn.execute(
            "SELECT COUNT(*) FROM vocab_choices WHERE item_id=? AND is_correct=1", (item_id,)
        ).fetchone()[0]
        total_ct = conn.execute(
            "SELECT COUNT(*) FROM vocab_choices WHERE item_id=?", (item_id,)
        ).fetchone()[0]
        if correct_ct != 1:
            item_issues.append(f"correct_choices={correct_ct}")
        if total_ct < 4:
            item_issues.append(f"total_choices={total_ct}")

        passes = len(item_issues) == 0
        if item_issues:
            issues.extend([f"[{item_id}/{lemma}] {i}" for i in item_issues])

        item_results.append({
            "item_id": item_id,
            "lemma": lemma,
            "bin_name": bin_name,
            "live_ca": ca,
            "is_active": is_active,
            "total_choices": total_ct,
            "item_issues": item_issues,
            "passes": passes,
        })

    item_pass_count = sum(1 for r in item_results if r.get("passes"))
    chk(f"All 9 items pass post-activation checks", item_pass_count == 9, f"{item_pass_count}/9 pass")

    conn.close()

    overall = "GREEN" if not issues else "FAIL"

    # Write JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR, "verb_tranche1_post_activation_validation.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "overall": overall,
            "bank_counts": {
                "total_active": total_active,
                "verb_active": verb_active,
                "verb_10k": verb_10k,
                "noun_10k": noun_10k,
                "adverb_active": adverb_active,
            },
            "global_checks": [{"check": n, "result": r} for n, r in global_checks],
            "items": item_results,
            "issues": issues,
        }, f, indent=2, ensure_ascii=False)

    # Write MD
    md_lines = [
        "# Verb Tranche1 — Post-Activation Validation",
        "",
        f"**DB:** {args.db}",
        f"**Date:** 2026-04-19",
        f"**Overall:** {overall}",
        "",
        "## Bank Count Checks",
        "",
        "| Check | Result |",
        "|-------|--------|",
    ]
    for name, result in global_checks:
        md_lines.append(f"| {name} | {result} |")
    md_lines += [
        "",
        "## Per-Item Results",
        "",
        "| item_id | lemma | bin | CA | is_active | choices | PASS |",
        "|---------|-------|-----|----|-----------|---------|------|",
    ]
    for r in item_results:
        if "error" in r:
            md_lines.append(f"| {r['item_id']} | — | — | — | — | — | FAIL({r['error']}) |")
            continue
        md_lines.append(
            f"| {r['item_id']} | {r['lemma']} | {r['bin_name']} | {r['live_ca']} "
            f"| {r['is_active']} | {r['total_choices']} "
            f"| {'**PASS**' if r['passes'] else '**FAIL**'} |"
        )
    md_lines += ["", f"**{item_pass_count}/9 items PASS**", ""]
    if issues:
        md_lines += ["## Issues", ""]
        for i in issues:
            md_lines.append(f"- {i}")

    md_path = os.path.join(OUTPUT_DIR, "verb_tranche1_post_activation_validation.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    # Console
    print("=" * 60)
    print("STAGE 3 — LIVE POST-ACTIVATION VALIDATION")
    print("=" * 60)
    print()
    print("Bank counts:")
    print(f"  Total active:    {total_active}  (expected {EXPECTED_TOTAL_AFTER})")
    print(f"  Verb active:     {verb_active}  (expected {EXPECTED_VERB_AFTER})")
    print(f"  Verb/10K:        {verb_10k}  (expected {EXPECTED_VERB_10K_AFTER})")
    print(f"  noun/10K:        {noun_10k}  (expected {NOUN_10K_EXPECTED}, no drift)")
    print(f"  Adverbs:         {adverb_active}  (expected {ADVERB_EXPECTED}, no drift)")
    print()
    print("Per-item:")
    for r in item_results:
        status = "PASS" if r.get("passes") else "FAIL"
        print(f"  {status:<6} id={r['item_id']:<6} {r.get('lemma','?'):<15} is_active={r.get('is_active','?')}")
    print()
    print("Global checks:")
    for name, result in global_checks:
        ok = "PASS" in result
        print(f"  {'OK' if ok else 'FAIL':4}  {name}: {result}")
    print()
    if issues:
        print("ISSUES:")
        for i in issues:
            print(f"  - {i}")
    print(f"\nOVERALL: {overall}")
    print(f"\nArtifacts:")
    print(f"  {json_path}")
    print(f"  {md_path}")

    return 0 if overall == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main())
