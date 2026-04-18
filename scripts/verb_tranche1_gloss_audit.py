#!/usr/bin/env python3
"""
verb_tranche1_gloss_audit.py

Stage A audit: classify all inactive verbs in staging for tranche1 readiness.

Reuses evaluate_verb_ru_gloss from services/vocab_qa/verb_gloss_rules.py.
Targets is_active=0 verbs only (the inactive candidate pool).

Classification:
  READY   — gloss passes all rules, bin assigned, choice integrity OK,
             no transparency concern
  REVIEW  — gloss is ok/borderline but has a non-blocking concern:
             NULL bin, phrase gloss, reflexive form, soft cognate signal
  REJECT  — hard rule failure: bad gloss, missing correct answer,
             choice integrity failure, strong cognate / translit flag

Artifacts written to --output-dir:
  verb_tranche1_gloss_audit.json         (per-item detail)
  verb_tranche1_gloss_audit_summary.md   (human-readable summary)
  verb_tranche1_candidate_classes.csv    (machine-readable per-item table)

SAFETY
  Strictly read-only. Connects via sqlite3 URI mode=ro. Zero DB writes.

USAGE
  python3 scripts/verb_tranche1_gloss_audit.py
  python3 scripts/verb_tranche1_gloss_audit.py --db data/lingua_staging.db \\
      --output-dir diagnostics_exports/verb_tranche1/current/
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import sqlite3
import sys

from services.vocab_qa.verb_gloss_rules import evaluate_verb_ru_gloss

DB_PATH_DEFAULT = "data/lingua_staging.db"
OUTPUT_DIR_DEFAULT = "diagnostics_exports/verb_tranche1/current"

BINS_ORDERED = ["1K", "2K", "5K", "10K", "20K"]

# Portuguese suffixes that indicate morphological transparency to international-word-aware learners.
COGNATE_RISK_PT_SUFFIXES = ("izar", "ificar", "ionar", "ualizar", "nalizar")
# Russian gloss patterns that are international roots (recognisable via English/French).
COGNATE_RISK_RU_RE = re.compile(
    r"(ировать|изировать|ифицировать|ционировать|улировать|нализировать)$"
)

# Verbs whose Portuguese form is a close cognate of their Russian translation
# (recognisable without knowing Russian, e.g. via English).
KNOWN_TRANSPARENT_PAIRS: set[tuple[str, str]] = {
    ("organizar", "организовать"),
    ("verificar", "проверить"),
    ("participar", "участвовать"),
    ("comunicar", "сообщать"),
    ("controlar", "контролировать"),
    ("decidir", "решить"),
    ("existir", "существовать"),
    ("funcionar", "работать"),
}


def _choice_count(conn: sqlite3.Connection, item_id: int) -> tuple[int, int]:
    """Return (total_choices, correct_choices) for item_id."""
    total = conn.execute(
        "SELECT COUNT(*) FROM vocab_choices WHERE item_id=?", (item_id,)
    ).fetchone()[0]
    correct = conn.execute(
        "SELECT COUNT(*) FROM vocab_choices WHERE item_id=? AND is_correct=1", (item_id,)
    ).fetchone()[0]
    return int(total), int(correct)


def _get_correct_answer(conn: sqlite3.Connection, item_id: int) -> str | None:
    row = conn.execute(
        "SELECT choice_text FROM vocab_choices WHERE item_id=? AND is_correct=1 LIMIT 1",
        (item_id,),
    ).fetchone()
    return row[0] if row else None


def _cognate_flags(lemma: str, gloss: str) -> list[str]:
    flags = []
    lemma_lower = (lemma or "").lower()
    gloss_norm = (gloss or "").strip().lower()
    for suffix in COGNATE_RISK_PT_SUFFIXES:
        if lemma_lower.endswith(suffix):
            flags.append(f"pt_suffix:{suffix}")
    if COGNATE_RISK_RU_RE.search(gloss_norm):
        flags.append("ru_internationalism")
    if (lemma_lower, gloss_norm) in KNOWN_TRANSPARENT_PAIRS:
        flags.append("known_transparent_pair")
    return flags


def classify_item(
    *,
    item_id: int,
    lemma: str,
    bin_name: str | None,
    correct_answer: str | None,
    total_choices: int,
    correct_choices: int,
    rule_result,
    cognate_flags: list[str],
) -> tuple[str, list[str]]:
    """
    Return (class, reasons) where class is READY | REVIEW | REJECT.
    Reasons are non-empty strings explaining the classification.
    """
    reasons: list[str] = []

    # --- Hard REJECT conditions ---
    if correct_answer is None:
        return "REJECT", ["no_correct_answer_in_vocab_choices"]

    if correct_choices != 1:
        reasons.append(f"choice_integrity:correct_count={correct_choices}_expected_1")
        return "REJECT", reasons

    if total_choices < 4:
        reasons.append(f"choice_integrity:total={total_choices}_below_4")
        return "REJECT", reasons

    if rule_result.status == "reject":
        reasons.append(f"gloss_rule:reject:flags={','.join(rule_result.flags)}")
        return "REJECT", reasons

    # Strong cognate flags escalate to REJECT only if both translit and phonetic copy fire.
    # (Pure internationalism is REVIEW, not REJECT — measurement is weakened but not broken.)

    # --- REVIEW conditions (non-blocking but require human check) ---
    if bin_name is None:
        reasons.append("bin_null:cannot_be_targeted_by_selector")
        return "REVIEW", reasons

    if rule_result.status == "review":
        reasons.extend([f"gloss_rule:{f}" for f in rule_result.flags])
        return "REVIEW", reasons

    if rule_result.risk_score >= 50:
        reasons.append(f"risk_score:{rule_result.risk_score}")
        return "REVIEW", reasons

    if total_choices not in (4, 6):
        reasons.append(f"choice_count:{total_choices}_unusual")
        return "REVIEW", reasons

    if cognate_flags:
        # Soft signal: internationalism weakens measurement but doesn't break it.
        # Mark REVIEW so a human can decide whether it's acceptable at this band.
        reasons.extend(cognate_flags)
        return "REVIEW", reasons

    if "reflexive_infinitive" in rule_result.flags:
        reasons.append("reflexive_infinitive:acceptable_but_flag_for_review")
        return "REVIEW", reasons

    if "phrase_like_gloss" in rule_result.flags:
        reasons.append("phrase_gloss:review_for_clarity")
        return "REVIEW", reasons

    # --- READY ---
    return "READY", []


def audit_inactive_verbs(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, lemma, pos, bin_name FROM vocab_items "
        "WHERE pos='verb' AND is_active=0 ORDER BY bin_name NULLS LAST, id"
    ).fetchall()

    results = []
    for row in rows:
        item_id = row["id"]
        lemma = row["lemma"]
        bin_name = row["bin_name"]
        correct_answer = _get_correct_answer(conn, item_id)
        total_choices, correct_choices = _choice_count(conn, item_id)

        gloss = correct_answer if correct_answer else lemma
        rule_result = evaluate_verb_ru_gloss(lemma=lemma, pos="verb", gloss=gloss)
        cognate_fl = _cognate_flags(lemma, gloss)

        item_class, reasons = classify_item(
            item_id=item_id,
            lemma=lemma,
            bin_name=bin_name,
            correct_answer=correct_answer,
            total_choices=total_choices,
            correct_choices=correct_choices,
            rule_result=rule_result,
            cognate_flags=cognate_fl,
        )

        results.append({
            "item_id": item_id,
            "lemma": lemma,
            "bin_name": bin_name,
            "correct_answer": correct_answer,
            "total_choices": total_choices,
            "correct_choices": correct_choices,
            "rule_status": rule_result.status,
            "rule_risk_score": rule_result.risk_score,
            "rule_flags": rule_result.flags,
            "cognate_flags": cognate_fl,
            "candidate_class": item_class,
            "reasons": reasons,
        })

    return results


def write_artifacts(results: list[dict], output_dir: str) -> dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)

    # ---- verb_tranche1_gloss_audit.json ----
    audit_json_path = os.path.join(output_dir, "verb_tranche1_gloss_audit.json")
    with open(audit_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # ---- verb_tranche1_candidate_classes.csv ----
    csv_path = os.path.join(output_dir, "verb_tranche1_candidate_classes.csv")
    csv_fields = [
        "item_id", "lemma", "bin_name", "correct_answer",
        "total_choices", "correct_choices",
        "rule_status", "rule_risk_score", "rule_flags",
        "cognate_flags", "candidate_class", "reasons",
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in results:
            writer.writerow({
                **r,
                "rule_flags": "|".join(r["rule_flags"]),
                "cognate_flags": "|".join(r["cognate_flags"]),
                "reasons": "|".join(r["reasons"]),
            })

    return {"audit_json": audit_json_path, "candidate_csv": csv_path}


def build_summary(results: list[dict], output_dir: str, db_path: str) -> dict:
    total = len(results)
    by_class: dict[str, list[dict]] = {"READY": [], "REVIEW": [], "REJECT": []}
    by_bin: dict[str, dict[str, int]] = {}
    flag_counts: dict[str, int] = {}

    for r in results:
        cls = r["candidate_class"]
        by_class[cls].append(r)
        bin_key = r["bin_name"] or "NULL"
        if bin_key not in by_bin:
            by_bin[bin_key] = {"READY": 0, "REVIEW": 0, "REJECT": 0}
        by_bin[bin_key][cls] += 1
        for fl in r["rule_flags"] + r["cognate_flags"]:
            flag_counts[fl] = flag_counts.get(fl, 0) + 1

    ready_10k = by_bin.get("10K", {}).get("READY", 0)
    ready_20k = by_bin.get("20K", {}).get("READY", 0)
    review_10k = by_bin.get("10K", {}).get("REVIEW", 0)
    review_20k = by_bin.get("20K", {}).get("REVIEW", 0)

    top_flags = sorted(flag_counts.items(), key=lambda kv: -kv[1])[:10]
    stage_b_justified = (ready_10k + ready_20k + review_10k + review_20k) >= 5

    summary = {
        "audit_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "db_path": db_path,
        "scope": "inactive verbs (is_active=0, pos=verb)",
        "total_audited": total,
        "by_class": {cls: len(items) for cls, items in by_class.items()},
        "by_bin_and_class": by_bin,
        "top_flags": dict(top_flags),
        "stage_b_recommendation": {
            "justified": stage_b_justified,
            "ready_10k": ready_10k,
            "ready_20k": ready_20k,
            "review_10k_may_pass_human_check": review_10k,
            "review_20k_may_pass_human_check": review_20k,
            "reason": (
                "Stage B is justified: sufficient READY/REVIEW items in 10K+20K to assemble a candidate pool."
                if stage_b_justified else
                "Stage B not yet justified: fewer than 5 READY/REVIEW items in 10K+20K combined. "
                "Fresh generation required before proceeding."
            ),
        },
    }

    # ---- verb_tranche1_gloss_audit_summary.md ----
    md_lines = [
        "# Verb Tranche1 Gloss Audit — Stage A Summary",
        "",
        f"**Audit date:** {summary['audit_date']}",
        f"**DB:** {db_path}",
        f"**Scope:** inactive verbs (`is_active=0`, `pos='verb'`)",
        "",
        "## Candidate Counts",
        "",
        f"| Class  | Count |",
        f"|--------|-------|",
    ]
    for cls in ("READY", "REVIEW", "REJECT"):
        md_lines.append(f"| {cls}   | {summary['by_class'][cls]} |")
    md_lines += [
        f"| **TOTAL** | **{total}** |",
        "",
        "## By Bin",
        "",
        "| Bin  | READY | REVIEW | REJECT | Total |",
        "|------|-------|--------|--------|-------|",
    ]
    bin_order = BINS_ORDERED + ["NULL"]
    for b in bin_order:
        if b not in by_bin:
            continue
        bdata = by_bin[b]
        row_total = bdata["READY"] + bdata["REVIEW"] + bdata["REJECT"]
        md_lines.append(
            f"| {b}   | {bdata['READY']} | {bdata['REVIEW']} | {bdata['REJECT']} | {row_total} |"
        )
    md_lines += [
        "",
        "## Top Rule Flags",
        "",
    ]
    for fl, cnt in top_flags:
        md_lines.append(f"- `{fl}`: {cnt} items")

    md_lines += [
        "",
        "## Stage B Recommendation",
        "",
        f"**Justified:** {'YES' if stage_b_justified else 'NO'}",
        "",
        summary["stage_b_recommendation"]["reason"],
        "",
        f"- READY in 10K: {ready_10k}",
        f"- READY in 20K: {ready_20k}",
        f"- REVIEW in 10K (may pass human check): {review_10k}",
        f"- REVIEW in 20K (may pass human check): {review_20k}",
        "",
        "## REJECT Detail",
        "",
        "Items in REJECT with their primary rejection reason:",
        "",
    ]
    for r in by_class["REJECT"]:
        md_lines.append(
            f"- `{r['lemma']}` (id={r['item_id']}, bin={r['bin_name']}): "
            f"{'; '.join(r['reasons']) or 'see rule_flags'}"
        )
    if not by_class["REJECT"]:
        md_lines.append("- _(none)_")

    md_lines += [
        "",
        "## REVIEW Items in Priority Bins (10K + 20K)",
        "",
        "These require human gloss check before Stage B inclusion:",
        "",
    ]
    priority_review = [
        r for r in by_class["REVIEW"]
        if r["bin_name"] in ("10K", "20K")
    ]
    if priority_review:
        for r in priority_review:
            md_lines.append(
                f"- `{r['lemma']}` (id={r['item_id']}, bin={r['bin_name']}, "
                f"gloss=`{r['correct_answer']}`): {'; '.join(r['reasons'])}"
            )
    else:
        md_lines.append("- _(none — all 10K/20K REVIEW items have NULL bin or other issue)_")

    os.makedirs(output_dir, exist_ok=True)
    md_path = os.path.join(output_dir, "verb_tranche1_gloss_audit_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    summary["_artifact_md"] = md_path
    return summary


def print_console_summary(summary: dict) -> None:
    SEP = "=" * 60
    print(SEP)
    print("VERB TRANCHE1 GLOSS AUDIT — STAGE A")
    print(SEP)
    print(f"\nDB:    {summary['db_path']}")
    print(f"Date:  {summary['audit_date']}")
    print(f"Scope: {summary['scope']}")
    print(f"\nTotal audited: {summary['total_audited']}")
    bc = summary["by_class"]
    print(f"  READY:  {bc['READY']}")
    print(f"  REVIEW: {bc['REVIEW']}")
    print(f"  REJECT: {bc['REJECT']}")

    print("\nBy bin:")
    for b in BINS_ORDERED + ["NULL"]:
        if b not in summary["by_bin_and_class"]:
            continue
        d = summary["by_bin_and_class"][b]
        t = d["READY"] + d["REVIEW"] + d["REJECT"]
        print(f"  {b:<4}  READY={d['READY']}  REVIEW={d['REVIEW']}  REJECT={d['REJECT']}  total={t}")

    print("\nTop flags:")
    for fl, cnt in summary["top_flags"].items():
        print(f"  {fl}: {cnt}")

    sb = summary["stage_b_recommendation"]
    print(f"\nStage B justified: {'YES' if sb['justified'] else 'NO'}")
    print(f"  {sb['reason']}")
    print(f"  READY 10K={sb['ready_10k']}  READY 20K={sb['ready_20k']}")
    print(f"  REVIEW 10K={sb['review_10k_may_pass_human_check']}  REVIEW 20K={sb['review_20k_may_pass_human_check']}")
    print(SEP)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage A: audit inactive verb pool for tranche1 readiness."
    )
    parser.add_argument("--db", default=DB_PATH_DEFAULT)
    parser.add_argument("--output-dir", default=OUTPUT_DIR_DEFAULT)
    parser.add_argument("--no-write", action="store_true",
                        help="Print to stdout only, do not write artifacts")
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    try:
        results = audit_inactive_verbs(conn)
    finally:
        conn.close()

    summary = build_summary(results, args.output_dir, args.db)

    if not args.no_write:
        paths = write_artifacts(results, args.output_dir)
        print_console_summary(summary)
        print(f"\nArtifacts written:")
        print(f"  {paths['audit_json']}")
        print(f"  {paths['candidate_csv']}")
        print(f"  {summary['_artifact_md']}")
    else:
        print_console_summary(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
