#!/usr/bin/env python3
"""
pos_next_track_audit_inspect.py

Read-only staging DB inspection for next-POS-track selection.
Outputs a structured JSON summary and a human-readable report to stdout.

Sections
  A  Active adverbs — full list with bin and correct_answer
  B  Active adverb bin summary with selector thin-bucket flags
  C  Active verbs — full list with basic cognate-risk heuristic
  D  Active verb bin summary with selector thin-bucket flags
  E  Inactive candidate pool counts by POS and bin
  F  -mente adverb contamination check (active + inactive)
  G  Anti-transparency heuristics: cognate and morphological transparency flags

SAFETY
  Strictly read-only. Zero DB writes.

USAGE
  python3 scripts/pos_next_track_audit_inspect.py
  python3 scripts/pos_next_track_audit_inspect.py --db data/lingua_staging.db
  python3 scripts/pos_next_track_audit_inspect.py --json-out diagnostics_exports/current/pos_audit_inspect.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys

DB_PATH_DEFAULT = "data/lingua_staging.db"
JSON_OUT_DEFAULT = "diagnostics_exports/current/pos_audit_inspect.json"

# Selector max_recent_exposure caps (from selector.py)
ADVERB_EXPOSURE_CAP = 8
VERB_EXPOSURE_CAP = 10

BINS_ORDERED = ["1K", "2K", "5K", "10K", "20K"]

# Basic cognate-risk heuristics: Portuguese suffixes that map
# transparently to Russian international roots or are recognisable
# via English/French cognates.
TRANSPARENT_PT_SUFFIXES = (
    "ar", "er", "ir",  # infinitive — NOT a cognate risk by itself
)
COGNATE_RISK_SUFFIXES_PT = (
    "izar", "ificar", "ionar",          # internationalisms: organizar, verificar
)
# Russian cognate targets that are highly recognisable to Slavic learners
COGNATE_RISK_RU_PATTERNS = re.compile(
    r"(ировать|изировать|ифицировать|ционировать)$"
)

# -mente pattern: adverbs derived from adjectives — morphological transparency risk
MENTE_PATTERN = re.compile(r"-?mente$", re.IGNORECASE)


def _bin_status(count: int, cap: int) -> str:
    if count == 0:
        return "EMPTY"
    if count <= cap:
        return "THIN"
    return "OK"


def _cognate_risk_flag(lemma: str, correct_answer: str) -> str | None:
    """Return a risk label if item shows basic cognate/transparency risk."""
    for suffix in COGNATE_RISK_SUFFIXES_PT:
        if lemma.lower().endswith(suffix):
            return f"PT_SUFFIX:{suffix}"
    if COGNATE_RISK_RU_PATTERNS.search(correct_answer or ""):
        return "RU_INTERNATIONALISM"
    return None


def audit(conn: sqlite3.Connection) -> dict:
    report: dict = {}

    # -----------------------------------------------------------------------
    # Section A + B: Active adverbs
    # -----------------------------------------------------------------------
    adverb_rows = conn.execute(
        "SELECT id, lemma, bin_name, correct_answer "
        "FROM vocab_items WHERE pos='adverb' AND is_active=1 "
        "ORDER BY bin_name, lemma"
    ).fetchall()

    adverb_list = []
    adverb_bin_counts: dict[str, int] = {b: 0 for b in BINS_ORDERED}
    adverb_bin_counts["NULL"] = 0

    for r in adverb_rows:
        risk = _cognate_risk_flag(r["lemma"], r["correct_answer"])
        entry = {
            "id": r["id"],
            "lemma": r["lemma"],
            "bin_name": r["bin_name"],
            "correct_answer": r["correct_answer"],
            "mente": bool(MENTE_PATTERN.search(r["lemma"] or "")),
            "cognate_risk": risk,
        }
        adverb_list.append(entry)
        bin_key = r["bin_name"] if r["bin_name"] in adverb_bin_counts else "NULL"
        adverb_bin_counts[bin_key] += 1

    adverb_bin_summary = []
    for b in BINS_ORDERED:
        cnt = adverb_bin_counts[b]
        adverb_bin_summary.append({
            "bin": b,
            "active_count": cnt,
            "selector_cap": ADVERB_EXPOSURE_CAP,
            "status": _bin_status(cnt, ADVERB_EXPOSURE_CAP),
        })

    report["section_A_active_adverbs"] = adverb_list
    report["section_B_adverb_bin_summary"] = adverb_bin_summary
    report["adverb_active_total"] = len(adverb_list)
    report["adverb_thin_bins"] = [e["bin"] for e in adverb_bin_summary if e["status"] == "THIN"]
    report["adverb_empty_bins"] = [e["bin"] for e in adverb_bin_summary if e["status"] == "EMPTY"]
    report["adverb_mente_active"] = [e for e in adverb_list if e["mente"]]
    report["adverb_cognate_risk_active"] = [e for e in adverb_list if e["cognate_risk"]]

    # -----------------------------------------------------------------------
    # Section C + D: Active verbs
    # -----------------------------------------------------------------------
    verb_rows = conn.execute(
        "SELECT id, lemma, bin_name, correct_answer "
        "FROM vocab_items WHERE pos='verb' AND is_active=1 "
        "ORDER BY bin_name, lemma"
    ).fetchall()

    verb_list = []
    verb_bin_counts: dict[str, int] = {b: 0 for b in BINS_ORDERED}
    verb_bin_counts["NULL"] = 0

    for r in verb_rows:
        risk = _cognate_risk_flag(r["lemma"], r["correct_answer"])
        entry = {
            "id": r["id"],
            "lemma": r["lemma"],
            "bin_name": r["bin_name"],
            "correct_answer": r["correct_answer"],
            "cognate_risk": risk,
        }
        verb_list.append(entry)
        bin_key = r["bin_name"] if r["bin_name"] in verb_bin_counts else "NULL"
        verb_bin_counts[bin_key] += 1

    verb_bin_summary = []
    for b in BINS_ORDERED:
        cnt = verb_bin_counts[b]
        verb_bin_summary.append({
            "bin": b,
            "active_count": cnt,
            "selector_cap": VERB_EXPOSURE_CAP,
            "status": _bin_status(cnt, VERB_EXPOSURE_CAP),
        })

    report["section_C_active_verbs"] = verb_list
    report["section_D_verb_bin_summary"] = verb_bin_summary
    report["verb_active_total"] = len(verb_list)
    report["verb_thin_bins"] = [e["bin"] for e in verb_bin_summary if e["status"] == "THIN"]
    report["verb_empty_bins"] = [e["bin"] for e in verb_bin_summary if e["status"] == "EMPTY"]
    report["verb_cognate_risk_active"] = [e for e in verb_list if e["cognate_risk"]]

    # -----------------------------------------------------------------------
    # Section E: Inactive candidate pools
    # -----------------------------------------------------------------------
    inactive_summary = {}
    for pos in ["verb", "adverb"]:
        total = conn.execute(
            "SELECT COUNT(*) AS cnt FROM vocab_items WHERE pos=? AND is_active=0",
            (pos,)
        ).fetchone()["cnt"]
        by_bin = {}
        for b in BINS_ORDERED:
            cnt = conn.execute(
                "SELECT COUNT(*) AS cnt FROM vocab_items WHERE pos=? AND is_active=0 AND bin_name=?",
                (pos, b)
            ).fetchone()["cnt"]
            by_bin[b] = cnt
        null_cnt = conn.execute(
            "SELECT COUNT(*) AS cnt FROM vocab_items WHERE pos=? AND is_active=0 AND bin_name IS NULL",
            (pos,)
        ).fetchone()["cnt"]
        by_bin["NULL"] = null_cnt
        inactive_summary[pos] = {"inactive_total": total, "by_bin": by_bin}

    report["section_E_inactive_pools"] = inactive_summary

    # -----------------------------------------------------------------------
    # Section F: -mente contamination check
    # -----------------------------------------------------------------------
    mente_active = conn.execute(
        "SELECT id, lemma, bin_name FROM vocab_items "
        "WHERE pos='adverb' AND is_active=1 AND lemma LIKE '%-mente'"
    ).fetchall()
    mente_inactive = conn.execute(
        "SELECT id, lemma, bin_name FROM vocab_items "
        "WHERE pos='adverb' AND is_active=0 AND lemma LIKE '%-mente'"
    ).fetchall()

    report["section_F_mente"] = {
        "active_mente_adverbs": [
            {"id": r["id"], "lemma": r["lemma"], "bin_name": r["bin_name"]}
            for r in mente_active
        ],
        "inactive_mente_adverbs_count": len(mente_inactive),
        "active_mente_count": len(mente_active),
    }

    # -----------------------------------------------------------------------
    # Section G: Summary risk table
    # -----------------------------------------------------------------------
    report["section_G_risk_summary"] = {
        "adverb": {
            "active_total": report["adverb_active_total"],
            "thin_bins": report["adverb_thin_bins"],
            "empty_bins": report["adverb_empty_bins"],
            "mente_active": len(report["adverb_mente_active"]),
            "cognate_risk_items": len(report["adverb_cognate_risk_active"]),
            "inactive_candidate_pool": inactive_summary["adverb"]["inactive_total"],
        },
        "verb": {
            "active_total": report["verb_active_total"],
            "thin_bins": report["verb_thin_bins"],
            "empty_bins": report["verb_empty_bins"],
            "cognate_risk_items": len(report["verb_cognate_risk_active"]),
            "inactive_candidate_pool": inactive_summary["verb"]["inactive_total"],
        },
    }

    return report


def print_human_summary(report: dict) -> None:
    SEP = "=" * 60

    print(SEP)
    print("POS NEXT TRACK AUDIT — INSPECT REPORT")
    print(SEP)

    print("\n--- SECTION A: ACTIVE ADVERBS (full list) ---")
    for e in report["section_A_active_adverbs"]:
        flags = []
        if e["mente"]:
            flags.append("MENTE")
        if e["cognate_risk"]:
            flags.append(f"COGNATE:{e['cognate_risk']}")
        flag_str = "  [" + ", ".join(flags) + "]" if flags else ""
        print(f"  {e['id']:>6}  {e['lemma']:<22}  {str(e['bin_name']):<5}  {e['correct_answer']}{flag_str}")

    print("\n--- SECTION B: ADVERB BIN SUMMARY ---")
    for e in report["section_B_adverb_bin_summary"]:
        print(f"  bin={e['bin']:<4}  active={e['active_count']:>3}  cap={e['selector_cap']}  [{e['status']}]")
    print(f"  TOTAL active adverbs: {report['adverb_active_total']}")
    print(f"  THIN bins: {report['adverb_thin_bins']}")
    print(f"  EMPTY bins: {report['adverb_empty_bins']}")

    print("\n--- SECTION C: ACTIVE VERBS (full list) ---")
    for e in report["section_C_active_verbs"]:
        flag_str = f"  [COGNATE:{e['cognate_risk']}]" if e["cognate_risk"] else ""
        print(f"  {e['id']:>6}  {e['lemma']:<22}  {str(e['bin_name']):<5}  {e['correct_answer']}{flag_str}")

    print("\n--- SECTION D: VERB BIN SUMMARY ---")
    for e in report["section_D_verb_bin_summary"]:
        print(f"  bin={e['bin']:<4}  active={e['active_count']:>3}  cap={e['selector_cap']}  [{e['status']}]")
    print(f"  TOTAL active verbs: {report['verb_active_total']}")
    print(f"  THIN bins: {report['verb_thin_bins']}")
    print(f"  EMPTY bins: {report['verb_empty_bins']}")

    print("\n--- SECTION E: INACTIVE CANDIDATE POOLS ---")
    for pos, data in report["section_E_inactive_pools"].items():
        print(f"  {pos.upper()} inactive_total={data['inactive_total']}")
        for b, cnt in data["by_bin"].items():
            if cnt > 0:
                print(f"    bin={b}: {cnt}")

    print("\n--- SECTION F: -MENTE CONTAMINATION ---")
    f = report["section_F_mente"]
    print(f"  Active -mente adverbs: {f['active_mente_count']}")
    for e in f["active_mente_adverbs"]:
        print(f"    {e['id']}  {e['lemma']}  {e['bin_name']}")
    print(f"  Inactive -mente adverbs (pool): {f['inactive_mente_adverbs_count']}")

    print("\n--- SECTION G: RISK SUMMARY ---")
    for pos, data in report["section_G_risk_summary"].items():
        print(f"  {pos.upper()}")
        for k, v in data.items():
            print(f"    {k}: {v}")

    print(f"\n{SEP}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only POS next-track audit inspect."
    )
    parser.add_argument("--db", default=DB_PATH_DEFAULT)
    parser.add_argument("--json-out", default=JSON_OUT_DEFAULT)
    parser.add_argument("--no-write", action="store_true",
                        help="Print to stdout only, do not write JSON")
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    try:
        report = audit(conn)
    finally:
        conn.close()

    print_human_summary(report)

    if not args.no_write:
        os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nJSON written to: {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
