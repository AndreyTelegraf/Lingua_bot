#!/usr/bin/env python3
"""
verb_tranche1_live_validate.py

STAGE 3 — Live DB validation after remediation apply.
Reads live DB state and checks:
  1. All 9 target items still is_active=0
  2. Remediated CAs match manifest
  3. Remediated distractors match proposals (by choice_id)
  4. Rule 1a passes for each item
  5. Rule 1b passes for each item
  6. Choice integrity: exactly 1 correct choice per item, total choices intact
  7. Manifest/live DB consistency confirmed

Outputs:
  diagnostics_exports/verb_tranche1/current/remediation_live_validation.json
  diagnostics_exports/verb_tranche1/current/remediation_live_validation.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
MANIFEST_PATH = "diagnostics_exports/verb_tranche1/current/verb_tranche1_post_remediation_manifest.json"
PROPOSALS_PATH = "diagnostics_exports/verb_tranche1/current/verb_tranche1_remediation_proposals.json"
OUTPUT_DIR = "diagnostics_exports/verb_tranche1/current"

TARGET_IDS = [868, 921, 1732, 1759, 2172, 3467, 3491, 3509, 9328]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_PATH)
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    manifest_by_id = {m["item_id"]: m for m in manifest["items"]}

    with open(PROPOSALS_PATH) as f:
        proposals = json.load(f)
    proposals_by_id = {p["item_id"]: p for p in proposals}

    # Active bank sets (unchanged items)
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

    item_results = []

    for item_id in TARGET_IDS:
        checks: dict[str, object] = {}
        item_issues: list[str] = []

        # Fetch live item row
        item_row = conn.execute(
            "SELECT id, lemma, correct_answer, is_active, bin_name FROM vocab_items WHERE id=?",
            (item_id,)
        ).fetchone()
        if item_row is None:
            item_results.append({"item_id": item_id, "error": "NOT_FOUND", "passes": False})
            continue

        live_ca = (item_row["correct_answer"] or "").strip()
        live_is_active = item_row["is_active"]
        live_lemma = item_row["lemma"]
        live_bin = item_row["bin_name"]

        # Check 1: is_active=0
        checks["is_active_zero"] = live_is_active == 0
        if live_is_active != 0:
            item_issues.append(f"is_active={live_is_active} (expected 0)")

        # Check 2: CA matches manifest
        manifest_ca = manifest_by_id[item_id]["chosen_ca"]
        checks["ca_matches_manifest"] = live_ca == manifest_ca
        if live_ca != manifest_ca:
            item_issues.append(f"CA mismatch: live='{live_ca}' manifest='{manifest_ca}'")

        # Check 3: Rule 1a (CA not in active distractors)
        checks["r1a_pass"] = live_ca not in active_distractors
        if live_ca in active_distractors:
            item_issues.append(f"R1a FAIL: CA '{live_ca}' is in active distractors")

        # Fetch live choices
        choice_rows = conn.execute(
            "SELECT id, choice_text, is_correct FROM vocab_choices WHERE item_id=? ORDER BY id",
            (item_id,)
        ).fetchall()
        correct_choices = [c for c in choice_rows if c["is_correct"] == 1]
        distractor_choices = [c for c in choice_rows if c["is_correct"] == 0]

        # Check 4: exactly 1 correct choice, matches CA
        checks["correct_choice_count"] = len(correct_choices) == 1
        if len(correct_choices) != 1:
            item_issues.append(f"correct_choice count={len(correct_choices)} (expected 1)")
        elif (correct_choices[0]["choice_text"] or "").strip() != live_ca:
            checks["correct_choice_text_matches_ca"] = False
            item_issues.append(
                f"correct choice text='{correct_choices[0]['choice_text']}' != CA='{live_ca}'"
            )
        else:
            checks["correct_choice_text_matches_ca"] = True

        # Check 5: distractor count matches proposal (5 expected for all items)
        expected_dist_count = len(proposals_by_id[item_id]["distractor_proposals"])
        checks["distractor_count"] = len(distractor_choices) == expected_dist_count
        if len(distractor_choices) != expected_dist_count:
            item_issues.append(f"distractor count={len(distractor_choices)} expected={expected_dist_count}")

        # Check 6: each proposed distractor replacement matches live DB by choice_id
        live_by_choice_id = {c["id"]: (c["choice_text"] or "").strip() for c in distractor_choices}
        distractor_match_details = []
        dist_matches_ok = True
        for dp in proposals_by_id[item_id]["distractor_proposals"]:
            cid = dp["choice_id"]
            expected_text = (dp["replacement"] or "").strip()
            live_text = live_by_choice_id.get(cid)
            match = live_text == expected_text
            distractor_match_details.append({
                "choice_id": cid,
                "expected": expected_text,
                "live": live_text,
                "match": match,
            })
            if not match:
                dist_matches_ok = False
                item_issues.append(
                    f"choice_id={cid} live='{live_text}' expected='{expected_text}'"
                )
        checks["distractor_texts_match_proposals"] = dist_matches_ok

        # Check 7: Rule 1b (no distractor is in active CAs)
        live_distractor_texts = [live_by_choice_id.get(c["id"], "") for c in distractor_choices]
        r1b_hits = [d for d in live_distractor_texts if d and d in active_cas]
        checks["r1b_pass"] = len(r1b_hits) == 0
        if r1b_hits:
            item_issues.append(f"R1b FAIL: distractors in active CAs: {r1b_hits}")

        # Check 8: manifest final_distractors match live
        manifest_distractors = set(manifest_by_id[item_id]["final_distractors"])
        live_distractor_set = set(live_distractor_texts)
        checks["manifest_distractors_match_live"] = manifest_distractors == live_distractor_set
        if manifest_distractors != live_distractor_set:
            diff = manifest_distractors.symmetric_difference(live_distractor_set)
            item_issues.append(f"manifest/live distractor mismatch: {diff}")

        passes = len(item_issues) == 0

        item_results.append({
            "item_id": item_id,
            "lemma": live_lemma,
            "bin_name": live_bin,
            "live_ca": live_ca,
            "live_is_active": live_is_active,
            "checks": checks,
            "issues": item_issues,
            "distractor_match_details": distractor_match_details,
            "passes": passes,
        })

    conn.close()

    pass_count = sum(1 for r in item_results if r.get("passes"))
    fail_count = len(item_results) - pass_count

    # Write JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR, "remediation_live_validation.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(item_results),
            "pass": pass_count,
            "fail": fail_count,
            "items": item_results,
        }, f, indent=2, ensure_ascii=False)

    # Write MD
    md_lines = [
        "# Verb Tranche1 Remediation — Live Validation",
        "",
        f"**DB:** {args.db}",
        f"**Date:** 2026-04-19",
        "",
        "## Per-Item Results",
        "",
        "| item_id | lemma | bin | live CA | is_active | R1a | R1b | dist_match | PASS |",
        "|---------|-------|-----|---------|-----------|-----|-----|------------|------|",
    ]
    for r in item_results:
        if "error" in r:
            md_lines.append(f"| {r['item_id']} | — | — | — | — | — | — | — | FAIL({r['error']}) |")
            continue
        c = r["checks"]
        md_lines.append(
            f"| {r['item_id']} | {r['lemma']} | {r['bin_name']} | {r['live_ca']} "
            f"| {'0 ✓' if c.get('is_active_zero') else 'FAIL'} "
            f"| {'✓' if c.get('r1a_pass') else 'FAIL'} "
            f"| {'✓' if c.get('r1b_pass') else 'FAIL'} "
            f"| {'✓' if c.get('distractor_texts_match_proposals') else 'FAIL'} "
            f"| {'**PASS**' if r['passes'] else '**FAIL**'} |"
        )
    md_lines += [
        "",
        f"## Summary: {pass_count}/{len(item_results)} PASS",
        "",
    ]
    for r in item_results:
        if r.get("issues"):
            md_lines += [f"### {r['lemma']} (id={r['item_id']}) ISSUES", ""]
            for issue in r["issues"]:
                md_lines.append(f"- {issue}")
            md_lines.append("")

    md_path = os.path.join(OUTPUT_DIR, "remediation_live_validation.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    # Console
    print("=" * 60)
    print("STAGE 3 — LIVE VALIDATION")
    print("=" * 60)
    for r in item_results:
        if "error" in r:
            print(f"  FAIL   id={r['item_id']} ERROR={r['error']}")
            continue
        status = "PASS" if r["passes"] else "FAIL"
        issues_str = f"  issues={r['issues']}" if r["issues"] else ""
        print(f"  {status:<6} id={r['item_id']:<6} {r['lemma']:<15} CA={r['live_ca']}{issues_str}")
    print()
    print(f"PASS: {pass_count}/{len(item_results)}")
    print(f"FAIL: {fail_count}/{len(item_results)}")
    print()
    print("Artifacts:")
    print(f"  {json_path}")
    print(f"  {md_path}")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
