#!/usr/bin/env python3
"""
verb_tranche1_prepare.py

STAGE B — PREPARE ONLY. NO ACTIVATION.

Selects up to 10 items from the READY verb pool (Stage A output) and
produces an activation-ready pack: collision report, manifest, and a
DO-NOT-RUN apply script.

Input:
  Stage A audit JSON:  diagnostics_exports/verb_tranche1/current/verb_tranche1_gloss_audit.json
  Staging DB (read-only): data/lingua_staging.db

Selection algorithm:
  1. Load READY items from Stage A audit.
  2. Prioritise by bin: 10K first, 20K second, then 5K, 2K, 1K.
  3. Run per-item: duplicate-lemma check, Rule 1a, Rule 1b, choice integrity.
  4. Hard-block any item that fails any check.
  5. Assign concept_group = topic_tag from DB (NULL → unique per-item group).
  6. Select up to TRANCHE_SIZE items; max MAX_PER_GROUP per concept_group.
  7. Apply intra-tranche conflict avoidance: skip item if its correct_answer
     is already a distractor of a selected item (or vice versa).

SAFETY
  Read-only DB connection (sqlite3 URI mode=ro). Zero DB writes.

USAGE
  python3 scripts/verb_tranche1_prepare.py
  python3 scripts/verb_tranche1_prepare.py --db data/lingua_staging.db \\
      --audit-json diagnostics_exports/verb_tranche1/current/verb_tranche1_gloss_audit.json \\
      --output-dir diagnostics_exports/verb_tranche1/current/
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys

AUDIT_JSON_DEFAULT = "diagnostics_exports/verb_tranche1/current/verb_tranche1_gloss_audit.json"
DB_PATH_DEFAULT = "data/lingua_staging.db"
OUTPUT_DIR_DEFAULT = "diagnostics_exports/verb_tranche1/current"

TRANCHE_SIZE = 10
MAX_PER_GROUP = 2
BIN_PRIORITY = ["10K", "20K", "5K", "2K", "1K"]


# ---------------------------------------------------------------------------
# DB helpers (all read-only)
# ---------------------------------------------------------------------------


def load_active_bank(conn: sqlite3.Connection) -> dict:
    """All active items: correct_answers and distractor values."""
    active_items = conn.execute(
        "SELECT id, lemma, correct_answer FROM vocab_items WHERE is_active=1"
    ).fetchall()
    active_cas: dict[str, int] = {}
    for row in active_items:
        ca = (row["correct_answer"] or "").strip()
        if ca:
            active_cas[ca] = row["id"]

    active_distractors: dict[str, list[int]] = {}
    dist_rows = conn.execute(
        "SELECT vc.item_id, vc.choice_text "
        "FROM vocab_choices vc "
        "JOIN vocab_items vi ON vi.id=vc.item_id "
        "WHERE vi.is_active=1 AND vc.is_correct=0"
    ).fetchall()
    for row in dist_rows:
        text = (row["choice_text"] or "").strip()
        if text:
            active_distractors.setdefault(text, []).append(row["item_id"])

    return {
        "active_cas": active_cas,
        "active_distractors": active_distractors,
        "active_item_count": len(active_items),
    }


def get_item_topic_tag(conn: sqlite3.Connection, item_id: int) -> str | None:
    row = conn.execute(
        "SELECT topic_tag FROM vocab_items WHERE id=?", (item_id,)
    ).fetchone()
    return row["topic_tag"] if row else None


def get_item_choices(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT choice_text, is_correct FROM vocab_choices WHERE item_id=? ORDER BY id",
        (item_id,),
    ).fetchall()
    return [{"choice_text": r["choice_text"], "is_correct": r["is_correct"]} for r in rows]


# ---------------------------------------------------------------------------
# Collision checks
# ---------------------------------------------------------------------------


def check_rule1a(correct_answer: str, active_bank: dict) -> dict:
    """New correct_answer must not be an active distractor."""
    ca = correct_answer.strip()
    if ca in active_bank["active_distractors"]:
        conflicting = active_bank["active_distractors"][ca]
        return {"passes": False, "violation": f"'{ca}' is a distractor in active item(s) {conflicting}"}
    return {"passes": True, "violation": None}


def check_rule1b(choices: list[dict], active_bank: dict) -> dict:
    """No active correct_answer may appear as a distractor in the new item."""
    violations = []
    for c in choices:
        if c["is_correct"]:
            continue
        text = (c["choice_text"] or "").strip()
        if text and text in active_bank["active_cas"]:
            active_item_id = active_bank["active_cas"][text]
            violations.append(f"distractor '{text}' is CA of active item {active_item_id}")
    if violations:
        return {"passes": False, "violations": violations}
    return {"passes": True, "violations": []}


def check_duplicate_lemma(lemma: str, conn: sqlite3.Connection) -> dict:
    row = conn.execute(
        "SELECT id FROM vocab_items WHERE lemma=? AND is_active=1", (lemma,)
    ).fetchone()
    if row:
        return {"passes": False, "violation": f"lemma '{lemma}' already active (id={row['id']})"}
    return {"passes": True, "violation": None}


def check_choice_integrity(choices: list[dict], item_id: int) -> dict:
    """Verify item has >= 4 choices and exactly 1 correct."""
    if len(choices) < 4:
        return {"passes": False, "violation": f"only {len(choices)} choices (need >= 4)"}
    correct_count = sum(1 for c in choices if c["is_correct"])
    if correct_count != 1:
        return {"passes": False, "violation": f"found {correct_count} correct choices (need exactly 1)"}
    return {"passes": True, "violation": None}


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def sort_by_bin_priority(items: list[dict]) -> list[dict]:
    bin_rank = {b: i for i, b in enumerate(BIN_PRIORITY)}
    return sorted(items, key=lambda r: (bin_rank.get(r["bin_name"], 99), r["item_id"]))


def select_tranche(
    ready_items: list[dict],
    collision_results: dict[int, dict],
) -> list[dict]:
    eligible = [r for r in ready_items if collision_results[r["item_id"]]["eligible"]]
    ordered = sort_by_bin_priority(eligible)

    group_count: dict[str, int] = {}
    selected: list[dict] = []
    selected_cas: set[str] = set()
    selected_distractors: set[str] = set()

    for item in ordered:
        if len(selected) >= TRANCHE_SIZE:
            break

        cg = item["concept_group"]
        if group_count.get(cg, 0) >= MAX_PER_GROUP:
            continue

        ca = (item["correct_answer"] or "").strip()
        item_distractors = {
            (c["choice_text"] or "").strip()
            for c in item["choices"]
            if not c["is_correct"]
        }

        # Intra-tranche conflict: new item's CA is already a distractor in selected set
        if ca in selected_distractors:
            continue
        # Intra-tranche conflict: new item's distractors include a selected CA
        if item_distractors & selected_cas:
            continue

        group_count[cg] = group_count.get(cg, 0) + 1
        selected.append(item)
        selected_cas.add(ca)
        selected_distractors.update(item_distractors)

    return selected


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_prepare(
    conn: sqlite3.Connection,
    audit_json_path: str,
) -> dict:
    with open(audit_json_path, encoding="utf-8") as f:
        all_audited: list[dict] = json.load(f)

    ready_raw = [r for r in all_audited if r["candidate_class"] == "READY"]

    active_bank = load_active_bank(conn)

    # Enrich each READY item with DB data: choices, topic_tag, concept_group
    enriched: list[dict] = []
    for r in ready_raw:
        item_id = r["item_id"]
        choices = get_item_choices(conn, item_id)
        topic_tag = get_item_topic_tag(conn, item_id)
        concept_group = topic_tag if topic_tag else f"_solo_{item_id}"
        enriched.append({**r, "choices": choices, "concept_group": concept_group})

    # Per-item collision + integrity checks
    collision_results: dict[int, dict] = {}
    for item in enriched:
        item_id = item["item_id"]
        dup = check_duplicate_lemma(item["lemma"], conn)
        r1a = check_rule1a(item["correct_answer"] or "", active_bank)
        r1b = check_rule1b(item["choices"], active_bank)
        integrity = check_choice_integrity(item["choices"], item_id)
        eligible = dup["passes"] and r1a["passes"] and r1b["passes"] and integrity["passes"]
        collision_results[item_id] = {
            "item_id": item_id,
            "lemma": item["lemma"],
            "bin_name": item["bin_name"],
            "correct_answer": item["correct_answer"],
            "concept_group": item["concept_group"],
            "duplicate_lemma": dup,
            "rule1a": r1a,
            "rule1b": r1b,
            "choice_integrity": integrity,
            "eligible": eligible,
        }

    hard_blocked = [v for v in collision_results.values() if not v["eligible"]]
    eligible_count = sum(1 for v in collision_results.values() if v["eligible"])

    selected = select_tranche(enriched, collision_results)
    selected_ids = {r["item_id"] for r in selected}

    reserve = [
        r for r in enriched
        if r["item_id"] not in selected_ids
        and collision_results[r["item_id"]]["eligible"]
    ]

    return {
        "prepared_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "db_path": conn.execute("PRAGMA database_list").fetchone()[2],
        "audit_json_path": audit_json_path,
        "active_bank_size": active_bank["active_item_count"],
        "ready_pool_size": len(ready_raw),
        "hard_blocked_count": len(hard_blocked),
        "eligible_count": eligible_count,
        "selected_count": len(selected),
        "hard_blocked": hard_blocked,
        "collision_results": list(collision_results.values()),
        "selected": selected,
        "reserve": reserve,
    }


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------


def write_collision_report(pack: dict, output_dir: str) -> str:
    path = os.path.join(output_dir, "verb_tranche1_collision_report.json")
    out = {
        "prepared_at": pack["prepared_at"],
        "active_bank_size": pack["active_bank_size"],
        "ready_pool_size": pack["ready_pool_size"],
        "hard_blocked_count": pack["hard_blocked_count"],
        "eligible_count": pack["eligible_count"],
        "hard_blocked": pack["hard_blocked"],
        "full_collision_results": pack["collision_results"],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return path


def write_manifest_json(pack: dict, output_dir: str) -> str:
    path = os.path.join(output_dir, "verb_tranche1_manifest.json")
    out = {
        "prepared_at": pack["prepared_at"],
        "activation_status": "PREPARE_ONLY — DO NOT ACTIVATE without monitoring gate",
        "selected_count": pack["selected_count"],
        "selected": [
            {
                "item_id": r["item_id"],
                "lemma": r["lemma"],
                "bin_name": r["bin_name"],
                "correct_answer": r["correct_answer"],
                "concept_group": r["concept_group"],
                "total_choices": r["total_choices"],
            }
            for r in pack["selected"]
        ],
        "reserve_count": len(pack["reserve"]),
        "reserve": [
            {
                "item_id": r["item_id"],
                "lemma": r["lemma"],
                "bin_name": r["bin_name"],
                "correct_answer": r["correct_answer"],
            }
            for r in pack["reserve"]
        ],
        "selection_rules": [
            f"bin priority: {BIN_PRIORITY}",
            f"max {MAX_PER_GROUP} items per concept_group (topic_tag)",
            "exclude items failing Rule 1a, Rule 1b, duplicate lemma, or choice integrity",
            "intra-tranche conflict avoidance: no CA/distractor cross-use among selected",
        ],
        "activation_gate": (
            "Do not run apply script until verb monitoring runner reports "
            "PREPARE_NEXT_TRANCHE AND minimum sample gate is met "
            "(30 sessions, 3 users, 5 answers/item for Signal 4)."
        ),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return path


def write_apply_script(pack: dict, output_dir: str) -> str:
    path = os.path.join(output_dir, "verb_tranche1_apply_DONOTRUN.sh")
    selected = pack["selected"]
    item_ids = [str(r["item_id"]) for r in selected]
    ids_csv = ", ".join(item_ids)
    n = len(selected)
    prepared_at = pack["prepared_at"]

    lines = [
        "#!/usr/bin/env bash",
        "# ==============================================================================",
        "# DO NOT RUN -- PREPARE ONLY",
        "# ==============================================================================",
        "# Generated by verb_tranche1_prepare.py on " + prepared_at + ".",
        "# Activates verb tranche 1 items in data/lingua_staging.db.",
        "#",
        "# ACTIVATION IS NOT AUTHORIZED until all of the following are true:",
        "#   1. verb_monitoring_runner.py verdict = PREPARE_NEXT_TRANCHE",
        "#      (minimum 30 sessions, >= 3 real users)",
        "#   2. At least one of T1-T4 has fired",
        "#   3. No active item with pct_correct < 20%",
        "#   4. Rule 1 anti-collision re-check against expanded active bank complete",
        "#",
        "# Usage (dry-run, default):",
        "#   bash diagnostics_exports/verb_tranche1/current/verb_tranche1_apply_DONOTRUN.sh",
        "# Usage (apply -- only when authorized):",
        "#   bash diagnostics_exports/verb_tranche1/current/verb_tranche1_apply_DONOTRUN.sh --apply",
        "# ==============================================================================",
        "",
        "set -euo pipefail",
        "",
        'DB="data/lingua_staging.db"',
        "APPLY=0",
        "",
        'for arg in "$@"; do',
        '  case "$arg" in',
        "    --apply) APPLY=1 ;;",
        '    *) echo "Unknown argument: $arg"; exit 1 ;;',
        "  esac",
        "done",
        "",
        'echo "DO NOT RUN / PREPARE ONLY script for verb tranche 1"',
        'echo "DB: $DB"',
        "",
        "# " + str(n) + " selected items:",
        'SELECTED_IDS="' + ids_csv + '"',
        "",
        'echo ""',
        'echo "Items that would be activated:"',
    ]

    for r in selected:
        lines.append(
            'echo "  ' + str(r["item_id"]) + "  " + r["lemma"]
            + "  ca=" + (r["correct_answer"] or "") + "  bin=" + (r["bin_name"] or "")
            + '"'
        )

    lines += [
        "",
        'echo ""',
        'echo "Pre-flight checks..."',
        "",
        "# Check 1: all items exist with is_active=0 and pos=verb",
        'COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items'
        " WHERE id IN (" + ids_csv + ")"
        " AND pos='verb' AND is_active=0;\")",
        'if [ "$COUNT" -ne ' + str(n) + " ]; then",
        '  echo "FAIL: Expected ' + str(n) + ' inactive verb items, found $COUNT"',
        "  exit 1",
        "fi",
        '  echo "  PASS: ' + str(n) + " items found in DB with pos=verb AND is_active=0\"",
        "",
        "# Check 2: no active lemma duplicates",
        'DUP_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items vi1'
        " JOIN vocab_items vi2 ON vi1.lemma=vi2.lemma"
        " WHERE vi1.id IN (" + ids_csv + ")"
        ' AND vi2.is_active=1 AND vi1.id != vi2.id;")',
        'if [ "$DUP_COUNT" -ne 0 ]; then',
        '  echo "FAIL: $DUP_COUNT duplicate lemmas found in active bank"',
        "  exit 1",
        "fi",
        '  echo "  PASS: No duplicate lemmas in active bank"',
        "",
        "# Check 3: Rule 1a — new correct_answers not in any active distractor set",
        'R1A=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items vi_new'
        " JOIN vocab_choices vc ON vc.choice_text=vi_new.correct_answer"
        " JOIN vocab_items vi_act ON vi_act.id=vc.item_id"
        " WHERE vi_new.id IN (" + ids_csv + ")"
        ' AND vc.is_correct=0 AND vi_act.is_active=1;")',
        'if [ "$R1A" -ne 0 ]; then',
        '  echo "FAIL: Rule 1a -- $R1A new correct_answers appear in active distractors"',
        "  exit 1",
        "fi",
        '  echo "  PASS: Rule 1a"',
        "",
        "# Check 4: Rule 1b — active correct_answers not in new item distractors",
        'R1B=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_choices vc_new'
        " JOIN vocab_items vi_new ON vi_new.id=vc_new.item_id"
        " JOIN vocab_items vi_act ON vi_act.correct_answer=vc_new.choice_text"
        " WHERE vi_new.id IN (" + ids_csv + ")"
        ' AND vc_new.is_correct=0 AND vi_act.is_active=1;")',
        'if [ "$R1B" -ne 0 ]; then',
        '  echo "FAIL: Rule 1b -- $R1B active correct_answers in new distractors"',
        "  exit 1",
        "fi",
        '  echo "  PASS: Rule 1b"',
        "",
        "# Check 5: noun/10K wave1 untouched (guard rail)",
        'N10K=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items'
        " WHERE pos='noun' AND bin_name='10K' AND is_active=1;\")",
        'if [ "$N10K" -ne 13 ]; then',
        '  echo "FAIL: noun/10K wave1 guard: expected 13 active items, found $N10K"',
        "  exit 1",
        "fi",
        '  echo "  PASS: noun/10K wave1 guard (13 items intact)"',
        "",
        'echo ""',
        'if [ "$APPLY" -eq 0 ]; then',
        '  echo "DRY RUN -- no changes made."',
        '  echo "Re-run with --apply to activate ' + str(n) + ' verb tranche 1 items."',
        "  exit 0",
        "fi",
        "",
        '# ---- ACTIVATION (only reached with --apply) ----',
        'echo "Activating ' + str(n) + ' verb tranche 1 items..."',
        'sqlite3 "$DB" "UPDATE vocab_items SET is_active=1, updated_at=datetime(\'now\')'
        " WHERE id IN (" + ids_csv + ');\"',
        "",
        'ACTIVATED=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items'
        " WHERE id IN (" + ids_csv + ') AND is_active=1;")',
        'echo "Activated: $ACTIVATED items"',
        'if [ "$ACTIVATED" -ne ' + str(n) + " ]; then",
        '  echo "FAIL: Expected ' + str(n) + ' activated, found $ACTIVATED"',
        "  exit 1",
        "fi",
        "",
        'echo ""',
        'echo "Post-activation active verb count by bin:"',
        "for BIN in 1K 2K 5K 10K 20K; do",
        '  CNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE pos=\'verb\' AND bin_name=\'$BIN\' AND is_active=1;")',
        '  echo "  $BIN: $CNT"',
        "done",
        'echo "DONE -- verb tranche 1 activated."',
    ]

    script = "\n".join(lines) + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    os.chmod(path, 0o644)
    return path


def write_summary_md(pack: dict, output_dir: str) -> str:
    path = os.path.join(output_dir, "verb_tranche1_prepare_summary.md")
    selected = pack["selected"]
    lines = [
        "# Verb Tranche1 Prepare — Stage B Summary",
        "",
        f"**Prepared:** {pack['prepared_at']}",
        f"**DB:** {pack['db_path']}",
        f"**Status:** PREPARE_ONLY — DO NOT ACTIVATE",
        "",
        "## Counts",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Active bank size | {pack['active_bank_size']} |",
        f"| READY pool (Stage A) | {pack['ready_pool_size']} |",
        f"| Hard blocked (collision) | {pack['hard_blocked_count']} |",
        f"| Eligible | {pack['eligible_count']} |",
        f"| Selected | {pack['selected_count']} |",
        f"| Reserve | {len(pack['reserve'])} |",
        "",
        "## Selected Items",
        "",
        "| item_id | lemma | bin | correct_answer | concept_group |",
        "|---------|-------|-----|----------------|---------------|",
    ]
    for r in selected:
        lines.append(
            f"| {r['item_id']} | {r['lemma']} | {r['bin_name']} "
            f"| {r['correct_answer']} | {r['concept_group']} |"
        )

    lines += [
        "",
        "## By Bin",
        "",
        "| Bin | Selected |",
        "|-----|----------|",
    ]
    from collections import Counter
    bin_counts = Counter(r["bin_name"] for r in selected)
    for b in ["1K", "2K", "5K", "10K", "20K"]:
        if bin_counts.get(b, 0) > 0:
            lines.append(f"| {b} | {bin_counts[b]} |")

    if pack["hard_blocked"]:
        lines += [
            "",
            "## Hard Blocked",
            "",
        ]
        for hb in pack["hard_blocked"]:
            dup = hb["duplicate_lemma"]
            r1a = hb["rule1a"]
            r1b = hb["rule1b"]
            integ = hb["choice_integrity"]
            reasons = []
            if not dup["passes"]:
                reasons.append(dup["violation"])
            if not r1a["passes"]:
                reasons.append(r1a["violation"])
            if not r1b["passes"]:
                reasons.extend(r1b["violations"])
            if not integ["passes"]:
                reasons.append(integ["violation"])
            lines.append(f"- `{hb['lemma']}` (id={hb['item_id']}, bin={hb['bin_name']}): {'; '.join(reasons)}")

    lines += [
        "",
        "## Collision Check Results (all READY items)",
        "",
        "| item_id | lemma | bin | dup | R1a | R1b | integrity | eligible |",
        "|---------|-------|-----|-----|-----|-----|-----------|----------|",
    ]
    for cr in sorted(pack["collision_results"], key=lambda r: (r.get("bin_name") or "Z", r["item_id"])):
        lines.append(
            f"| {cr['item_id']} | {cr['lemma']} | {cr['bin_name']} "
            f"| {'✓' if cr['duplicate_lemma']['passes'] else '✗'} "
            f"| {'✓' if cr['rule1a']['passes'] else '✗'} "
            f"| {'✓' if cr['rule1b']['passes'] else '✗'} "
            f"| {'✓' if cr['choice_integrity']['passes'] else '✗'} "
            f"| {'YES' if cr['eligible'] else 'NO'} |"
        )

    lines += [
        "",
        "## Activation Gate",
        "",
        "**DO NOT RUN** `verb_tranche1_apply_DONOTRUN.sh` until:",
        "- `verb_monitoring_runner.py` verdict = `PREPARE_NEXT_TRANCHE`",
        "- Minimum 30 real sessions and 3 distinct users",
        "- No active item with `pct_correct < 20%`",
        "- Rule 1 re-check passes against the live active bank at activation time",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------


def print_console_summary(pack: dict) -> None:
    SEP = "=" * 60
    print(SEP)
    print("VERB TRANCHE1 — STAGE B PREPARE ONLY")
    print(f"Generated: {pack['prepared_at']}")
    print("STATUS: DO NOT ACTIVATE — prepare-only mode")
    print(SEP)
    print(f"\nActive bank:     {pack['active_bank_size']} items")
    print(f"READY pool:      {pack['ready_pool_size']} items")
    print(f"Hard blocked:    {pack['hard_blocked_count']}")
    print(f"Eligible:        {pack['eligible_count']}")
    print(f"\nSelected ({pack['selected_count']} items):")
    for r in pack["selected"]:
        print(
            f"  {r['item_id']:>6}  {r['lemma']:<22}  bin={r['bin_name']:<5} "
            f"ca={r['correct_answer']:<25}  cg={r['concept_group']}"
        )
    if pack["hard_blocked"]:
        print(f"\nHard blocked ({pack['hard_blocked_count']} items):")
        for hb in pack["hard_blocked"]:
            dup = hb["duplicate_lemma"]
            r1a = hb["rule1a"]
            r1b = hb["rule1b"]
            integ = hb["choice_integrity"]
            reasons = []
            if not dup["passes"]:
                reasons.append(dup["violation"])
            if not r1a["passes"]:
                reasons.append(r1a["violation"])
            if not r1b["passes"]:
                reasons.extend(r1b["violations"])
            if not integ["passes"]:
                reasons.append(integ["violation"])
            print(f"  {hb['item_id']}  {hb['lemma']}  {'; '.join(reasons)}")
    print(f"\nReserve: {len(pack['reserve'])} items available for tranche 2")
    print(f"\nActivation gate: DO NOT RUN apply script until monitoring runner")
    print(f"  reports PREPARE_NEXT_TRANCHE AND minimum sample is met.")
    print(SEP)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PREPARE ONLY: verb tranche1 preparation. No DB writes."
    )
    parser.add_argument("--db", default=DB_PATH_DEFAULT)
    parser.add_argument("--audit-json", default=AUDIT_JSON_DEFAULT)
    parser.add_argument("--output-dir", default=OUTPUT_DIR_DEFAULT)
    parser.add_argument("--no-write", action="store_true",
                        help="Print to stdout only, do not write artifacts")
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        return 1
    if not os.path.exists(args.audit_json):
        print(f"ERROR: audit JSON not found: {args.audit_json}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    try:
        pack = run_prepare(conn, args.audit_json)
    finally:
        conn.close()

    print_console_summary(pack)

    if not args.no_write:
        os.makedirs(args.output_dir, exist_ok=True)
        p1 = write_collision_report(pack, args.output_dir)
        p2 = write_manifest_json(pack, args.output_dir)
        p3 = write_apply_script(pack, args.output_dir)
        p4 = write_summary_md(pack, args.output_dir)
        print(f"\nArtifacts written:")
        print(f"  {p1}")
        print(f"  {p2}")
        print(f"  {p3}")
        print(f"  {p4}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
