#!/usr/bin/env python3
"""
verb_tranche1_build_activation_pack.py

Stage 2 — Activation pack generation. Read-only against DB.
Produces:
  verb_tranche1_activation_manifest.json
  verb_tranche1_activation_collision_report.json
  verb_tranche1_activation_summary.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
RECONFIRM_PATH = "diagnostics_exports/verb_tranche1/current/verb_tranche1_target_reconfirmation.md"
OUTPUT_DIR = "diagnostics_exports/verb_tranche1/current"

TARGET_IDS = [868, 921, 1732, 1759, 2172, 3467, 3491, 3509, 9328]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # Active bank sets
    active_cas: set[str] = set()
    active_ca_map: dict[str, int] = {}
    for row in conn.execute(
        "SELECT id, correct_answer FROM vocab_items WHERE is_active=1 AND correct_answer IS NOT NULL"
    ).fetchall():
        ca = (row["correct_answer"] or "").strip()
        if ca:
            active_cas.add(ca)
            active_ca_map[ca] = row["id"]

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

    active_verb_count = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='verb'"
    ).fetchone()[0]
    active_verb_10k = conn.execute(
        "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='verb' AND bin_name='10K'"
    ).fetchone()[0]

    manifest_items = []
    collision_items = []
    issues: list[str] = []
    tranche_cas: set[str] = set()
    tranche_distractors: set[str] = set()

    for item_id in TARGET_IDS:
        row = conn.execute(
            "SELECT id, lemma, pos, correct_answer, is_active, bin_name FROM vocab_items WHERE id=?",
            (item_id,)
        ).fetchone()
        if row is None:
            issues.append(f"item_id={item_id} NOT FOUND")
            continue

        lemma = (row["lemma"] or "").strip()
        pos = (row["pos"] or "").strip()
        ca = (row["correct_answer"] or "").strip()
        is_active = row["is_active"]
        bin_name = (row["bin_name"] or "").strip()

        choices = conn.execute(
            "SELECT id, choice_text, is_correct FROM vocab_choices WHERE item_id=? ORDER BY id",
            (item_id,)
        ).fetchall()
        correct_choices = [c for c in choices if c["is_correct"] == 1]
        distractor_choices = [c for c in choices if c["is_correct"] == 0]
        distractor_texts = [(c["choice_text"] or "").strip() for c in distractor_choices]

        # All checks
        chk_exists = True
        chk_pos_verb = pos == "verb"
        chk_is_active_zero = is_active == 0
        chk_no_dup_lemma = lemma not in active_lemmas
        chk_r1a = ca not in active_distractors
        r1b_hits = [d for d in distractor_texts if d and d in active_cas]
        chk_r1b = len(r1b_hits) == 0
        chk_correct_choice = len(correct_choices) == 1
        chk_total_choices = len(choices) >= 4
        intra_ca_conflict = ca in tranche_distractors
        intra_dist_hits = [d for d in distractor_texts if d in tranche_cas]
        chk_intra_ca = not intra_ca_conflict
        chk_intra_dist = len(intra_dist_hits) == 0

        item_issues = []
        if not chk_pos_verb:
            item_issues.append(f"pos='{pos}'")
        if not chk_is_active_zero:
            item_issues.append(f"is_active={is_active}")
        if not chk_no_dup_lemma:
            item_issues.append(f"dup_lemma='{lemma}'")
        if not chk_r1a:
            item_issues.append(f"R1a_fail: CA='{ca}'")
        if not chk_r1b:
            item_issues.append(f"R1b_fail: {r1b_hits}")
        if not chk_correct_choice:
            item_issues.append(f"correct_choices={len(correct_choices)}")
        if not chk_total_choices:
            item_issues.append(f"total_choices={len(choices)}")
        if not chk_intra_ca:
            item_issues.append(f"intra_ca_conflict: CA='{ca}'")
        if not chk_intra_dist:
            item_issues.append(f"intra_dist_conflict: {intra_dist_hits}")

        all_pass = len(item_issues) == 0
        if item_issues:
            issues.extend([f"[{item_id}/{lemma}] {i}" for i in item_issues])

        collision_items.append({
            "item_id": item_id,
            "lemma": lemma,
            "bin_name": bin_name,
            "correct_answer": ca,
            "checks": {
                "exists": chk_exists,
                "pos_verb": chk_pos_verb,
                "is_active_zero": chk_is_active_zero,
                "no_dup_lemma": chk_no_dup_lemma,
                "r1a_pass": chk_r1a,
                "r1b_pass": chk_r1b,
                "correct_choice_count": chk_correct_choice,
                "total_choices_ok": chk_total_choices,
                "intra_ca_clean": chk_intra_ca,
                "intra_dist_clean": chk_intra_dist,
            },
            "r1b_hits": r1b_hits,
            "intra_dist_hits": intra_dist_hits,
            "item_issues": item_issues,
            "passes": all_pass,
            "readiness_status": "ACTIVATION_READY_PREPARED" if all_pass else "BLOCKED",
        })

        manifest_items.append({
            "item_id": item_id,
            "lemma": lemma,
            "pos": pos,
            "bin_name": bin_name,
            "correct_answer": ca,
            "is_active": is_active,
            "total_choices": len(choices),
            "distractors": distractor_texts,
            "current_validation_status": "PASS" if all_pass else "FAIL",
            "readiness_status": "ACTIVATION_READY_PREPARED" if all_pass else "BLOCKED",
        })

        tranche_cas.add(ca)
        tranche_distractors.update(distractor_texts)

    conn.close()

    pass_count = sum(1 for c in collision_items if c["passes"])
    fail_count = len(collision_items) - pass_count
    overall = "GREEN" if not issues else "BLOCKED"

    post_verb_count = active_verb_count + pass_count
    post_verb_10k = active_verb_10k + sum(1 for m in manifest_items if m["bin_name"] == "10K" and m["readiness_status"] == "ACTIVATION_READY_PREPARED")

    # Write manifest
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    manifest_path = os.path.join(OUTPUT_DIR, "verb_tranche1_activation_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "tranche": "verb_tranche1",
            "total_items": len(manifest_items),
            "readiness_status": "ACTIVATION_READY_PREPARED",
            "bin_distribution": {
                b: sum(1 for m in manifest_items if m["bin_name"] == b)
                for b in sorted({m["bin_name"] for m in manifest_items})
            },
            "active_verb_count_before": active_verb_count,
            "active_verb_10k_before": active_verb_10k,
            "projected_verb_count_after": post_verb_count,
            "projected_verb_10k_after": post_verb_10k,
            "items": manifest_items,
        }, f, indent=2, ensure_ascii=False)

    # Write collision report
    collision_path = os.path.join(OUTPUT_DIR, "verb_tranche1_activation_collision_report.json")
    with open(collision_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(collision_items),
            "pass": pass_count,
            "fail": fail_count,
            "overall": overall,
            "items": collision_items,
        }, f, indent=2, ensure_ascii=False)

    # Write summary MD
    md_lines = [
        "# Verb Tranche1 — Activation Pack Summary",
        "",
        f"**DB:** {args.db}",
        f"**Date:** 2026-04-19",
        f"**Status:** {overall}",
        "",
        "## Collision Report",
        "",
        "| item_id | lemma | bin | CA | pos | is_active | no_dup | R1a | R1b | choices | readiness |",
        "|---------|-------|-----|----|-----|-----------|--------|-----|-----|---------|-----------|",
    ]
    for c in collision_items:
        chk = c["checks"]
        md_lines.append(
            f"| {c['item_id']} | {c['lemma']} | {c['bin_name']} | {c['correct_answer']} "
            f"| {'✓' if chk['pos_verb'] else 'FAIL'} "
            f"| {'0✓' if chk['is_active_zero'] else 'FAIL'} "
            f"| {'✓' if chk['no_dup_lemma'] else 'FAIL'} "
            f"| {'✓' if chk['r1a_pass'] else 'FAIL'} "
            f"| {'✓' if chk['r1b_pass'] else 'FAIL'} "
            f"| {'✓' if chk['correct_choice_count'] and chk['total_choices_ok'] else 'FAIL'} "
            f"| {c['readiness_status']} |"
        )
    md_lines += [
        "",
        f"**Result: {pass_count}/{len(collision_items)} PASS — {overall}**",
        "",
        "## Projected Verb Coverage After Activation",
        "",
        f"| Metric | Before | After |",
        f"|--------|--------|-------|",
        f"| Active verbs (all bins) | {active_verb_count} | {post_verb_count} |",
        f"| Active verbs (10K) | {active_verb_10k} | {post_verb_10k} |",
        "",
        "## Apply Script",
        "",
        "See `scripts/verb_tranche1_activate_DONOTRUN.sh`.",
        "Default behavior: dry-run only. Pass `--apply` to activate (not done in this task).",
        "",
    ]

    md_path = os.path.join(OUTPUT_DIR, "verb_tranche1_activation_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    # Console
    print("=" * 60)
    print("STAGE 2 — ACTIVATION PACK GENERATION")
    print("=" * 60)
    print(f"\nActive verbs before: {active_verb_count} (10K: {active_verb_10k})")
    print(f"Projected after activation: {post_verb_count} (10K: {post_verb_10k})")
    print()
    for c in collision_items:
        status = "PASS" if c["passes"] else "FAIL"
        print(f"  {status:<6} id={c['item_id']:<6} {c['lemma']:<15} {c['readiness_status']}")
    print()
    print(f"PASS: {pass_count}/{len(collision_items)}")
    print(f"OVERALL: {overall}")
    print()
    print("Artifacts:")
    print(f"  {manifest_path}")
    print(f"  {collision_path}")
    print(f"  {md_path}")

    return 0 if overall == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main())
