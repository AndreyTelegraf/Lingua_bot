#!/usr/bin/env python3
"""
noun10k_tranche2_prepare.py

STAGE 2 — PREPARE ONLY. NO ACTIVATION.

Prepares noun/10K tranche 2 from the remaining READY pool (items in DB with
is_active=0). Produces a manifest of selected candidates, a collision report,
and a DO-NOT-RUN apply script template.

SAFETY CONSTRAINTS
  - This script is read-only with respect to the database.
  - It does NOT write to the DB.
  - It does NOT set is_active=1 for any item.
  - The apply script it produces is explicitly marked DO NOT RUN.

USAGE
  python3 scripts/noun10k_tranche2_prepare.py
  python3 scripts/noun10k_tranche2_prepare.py --db data/lingua_staging.db
  python3 scripts/noun10k_tranche2_prepare.py --db data/lingua_staging.db \\
      --output-dir diagnostics_exports/current/

OUTPUT FILES
  noun10k_tranche2_collision_report.json  — Rule 1a + 1b check against live active bank
  noun10k_tranche2_manifest.json          — selected tranche 2 candidates with rationale
  noun10k_tranche2_manifest.csv           — CSV for human inspection
  noun10k_tranche2_apply_DONOTRUN.sh      — activation script (DO NOT RUN without monitoring gate)
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sqlite3
import sys

IMPORT_READY_CSV = "diagnostics_exports/current/import_ready.csv"

TRANCHE_SIZE = 10
MAX_PER_CONCEPT_GROUP = 2
NOUN_10K_POS = "noun"
NOUN_10K_BIN = "10K"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_active_bank(conn: sqlite3.Connection) -> dict:
    """Load active noun bank: correct_answers and distractor values."""
    active_items = conn.execute(
        "SELECT id, lemma, correct_answer FROM vocab_items "
        "WHERE is_active = 1"
    ).fetchall()

    active_cas: dict[str, int] = {}
    for row in active_items:
        ca = row["correct_answer"].strip()
        active_cas[ca] = row["id"]

    active_distractors: dict[str, list[int]] = {}
    distractor_rows = conn.execute(
        "SELECT vc.item_id, vc.choice_text "
        "FROM vocab_choices vc "
        "JOIN vocab_items vi ON vi.id = vc.item_id "
        "WHERE vi.is_active = 1 AND vc.is_correct = 0"
    ).fetchall()
    for row in distractor_rows:
        text = row["choice_text"].strip()
        if text not in active_distractors:
            active_distractors[text] = []
        active_distractors[text].append(row["item_id"])

    return {
        "active_cas": active_cas,
        "active_distractors": active_distractors,
        "active_item_count": len(active_items),
    }


def load_noun10k_active_ids(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute(
        "SELECT id FROM vocab_items WHERE pos = ? AND bin_name = ? AND is_active = 1",
        [NOUN_10K_POS, NOUN_10K_BIN],
    ).fetchall()
    return {r[0] for r in rows}


def load_candidates_from_csv(csv_path: str) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_inactive_noun10k_item_ids(conn: sqlite3.Connection) -> set[int]:
    rows = conn.execute(
        "SELECT id FROM vocab_items WHERE pos = ? AND bin_name = ? AND is_active = 0",
        [NOUN_10K_POS, NOUN_10K_BIN],
    ).fetchall()
    return {r[0] for r in rows}


def verify_item_in_db(conn: sqlite3.Connection, item_id: int) -> bool:
    row = conn.execute(
        "SELECT id FROM vocab_items WHERE id = ? AND pos = ? AND bin_name = ?",
        [item_id, NOUN_10K_POS, NOUN_10K_BIN],
    ).fetchone()
    return row is not None


def get_item_choices(conn: sqlite3.Connection, item_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT choice_text, is_correct FROM vocab_choices WHERE item_id = ? ORDER BY id",
        [item_id],
    ).fetchall()
    return [{"choice_text": r["choice_text"], "is_correct": r["is_correct"]} for r in rows]


# ---------------------------------------------------------------------------
# Collision checks
# ---------------------------------------------------------------------------


def check_rule1a(candidate: dict, active_bank: dict) -> dict:
    """Rule 1a: candidate's correct_answer must not appear as a distractor in any active item."""
    ca = candidate["correct_answer"].strip()
    if ca in active_bank["active_distractors"]:
        conflicting_item_ids = active_bank["active_distractors"][ca]
        return {
            "passes": False,
            "violation": f"correct_answer '{ca}' is a distractor in active item(s) {conflicting_item_ids}",
        }
    return {"passes": True, "violation": None}


def check_rule1b(candidate: dict, active_bank: dict) -> dict:
    """Rule 1b: no active item's correct_answer may appear as a distractor in the candidate."""
    candidate_distractors = [
        candidate.get("distractor_1", "").strip(),
        candidate.get("distractor_2", "").strip(),
        candidate.get("distractor_3", "").strip(),
    ]
    violations = []
    for d in candidate_distractors:
        if not d:
            continue
        if d in active_bank["active_cas"]:
            active_item_id = active_bank["active_cas"][d]
            violations.append(
                f"distractor '{d}' is the correct_answer of active item {active_item_id}"
            )
    if violations:
        return {"passes": False, "violations": violations}
    return {"passes": True, "violations": []}


def check_duplicate_lemma(candidate: dict, conn: sqlite3.Connection) -> dict:
    """Reject if lemma already exists in active bank."""
    row = conn.execute(
        "SELECT id FROM vocab_items WHERE lemma = ? AND is_active = 1",
        [candidate["lemma"]],
    ).fetchone()
    if row:
        return {"passes": False, "violation": f"lemma '{candidate['lemma']}' already active (id={row['id']})"}
    return {"passes": True, "violation": None}


def check_choice_integrity(conn: sqlite3.Connection, item_id: int) -> dict:
    """Verify item has exactly 4 choices, exactly 1 correct."""
    choices = get_item_choices(conn, item_id)
    if len(choices) != 4:
        return {"passes": False, "violation": f"expected 4 choices, found {len(choices)}"}
    correct_count = sum(1 for c in choices if c["is_correct"])
    if correct_count != 1:
        return {"passes": False, "violation": f"expected 1 correct choice, found {correct_count}"}
    return {"passes": True, "violation": None}


# ---------------------------------------------------------------------------
# Selection algorithm
# ---------------------------------------------------------------------------


def select_tranche2(
    candidates: list[dict],
    collision_results: list[dict],
) -> list[dict]:
    """
    Select up to TRANCHE_SIZE items using monitoring plan priorities:
    1. Prefer CLEAN over WARN (in collision_note column).
    2. Exclude any item with Rule 1b hard block against current active bank.
    3. Max MAX_PER_CONCEPT_GROUP items per concept_group.
    4. For WARN pairs among inactive items, include at most one side.
    """
    by_id = {r["item_id"]: r for r in collision_results}

    eligible = [c for c in candidates if by_id[int(c["import_item_id"])]["eligible"]]

    clean = [c for c in eligible if c["collision_note"] == "CLEAN"]
    warn = [c for c in eligible if "WARN" in c["collision_note"]]

    concept_group_count: dict[str, int] = {}
    selected: list[dict] = []
    selected_cas: set[str] = set()

    def _try_add(candidate: dict) -> bool:
        cg = candidate.get("concept_group", "unknown")
        if concept_group_count.get(cg, 0) >= MAX_PER_CONCEPT_GROUP:
            return False
        concept_group_count[cg] = concept_group_count.get(cg, 0) + 1
        selected.append(candidate)
        selected_cas.add(candidate["correct_answer"].strip())
        return True

    for c in clean:
        if len(selected) >= TRANCHE_SIZE:
            break
        _try_add(c)

    for c in warn:
        if len(selected) >= TRANCHE_SIZE:
            break
        distractors = [
            c.get("distractor_1", "").strip(),
            c.get("distractor_2", "").strip(),
            c.get("distractor_3", "").strip(),
        ]
        conflict_with_selected = any(d in selected_cas for d in distractors if d)
        ca_in_selected_distractors = False
        ca = c["correct_answer"].strip()
        for sel in selected:
            sel_distractors = [
                sel.get("distractor_1", "").strip(),
                sel.get("distractor_2", "").strip(),
                sel.get("distractor_3", "").strip(),
            ]
            if ca in sel_distractors:
                ca_in_selected_distractors = True
                break
        if conflict_with_selected or ca_in_selected_distractors:
            continue
        _try_add(c)

    return selected


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def build_tranche2_pack(conn: sqlite3.Connection, csv_path: str) -> dict:
    active_bank = load_active_bank(conn)
    active_noun10k_ids = load_noun10k_active_ids(conn)
    inactive_noun10k_ids = load_inactive_noun10k_item_ids(conn)

    all_csv_rows = load_candidates_from_csv(csv_path)
    ready_rows = [r for r in all_csv_rows if r["import_status"] == "READY"]

    # Partition: already active vs remaining pool
    already_active = [r for r in ready_rows if int(r["import_item_id"]) in active_noun10k_ids]
    remaining = [r for r in ready_rows if int(r["import_item_id"]) not in active_noun10k_ids]

    # Collision checks per candidate
    collision_results = []
    for r in remaining:
        item_id = int(r["import_item_id"])
        in_db = item_id in inactive_noun10k_ids
        r1a = check_rule1a(r, active_bank)
        r1b = check_rule1b(r, active_bank)
        dup = check_duplicate_lemma(r, conn)
        integrity = check_choice_integrity(conn, item_id) if in_db else {"passes": False, "violation": "item not in DB"}

        eligible = r1a["passes"] and r1b["passes"] and dup["passes"] and integrity["passes"]

        collision_results.append({
            "item_id": item_id,
            "lemma": r["lemma"],
            "correct_answer": r["correct_answer"],
            "concept_group": r.get("concept_group", ""),
            "collision_note_csv": r["collision_note"],
            "in_db": in_db,
            "rule1a": r1a,
            "rule1b": r1b,
            "duplicate_lemma": dup,
            "choice_integrity": integrity,
            "eligible": eligible,
        })

    hard_blocked = [c for c in collision_results if not c["eligible"]]
    eligible_count = sum(1 for c in collision_results if c["eligible"])

    selected = select_tranche2(remaining, collision_results)
    selected_ids = {int(r["import_item_id"]) for r in selected}

    unselected_eligible = [
        r for r in remaining
        if int(r["import_item_id"]) not in selected_ids
        and next(c for c in collision_results if c["item_id"] == int(r["import_item_id"]))["eligible"]
    ]

    return {
        "prepared_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "db_path": conn.execute("PRAGMA database_list").fetchone()[2],
        "csv_path": csv_path,
        "active_bank_size": active_bank["active_item_count"],
        "active_noun10k_count": len(active_noun10k_ids),
        "already_active_from_csv": len(already_active),
        "remaining_pool_size": len(remaining),
        "hard_blocked_count": len(hard_blocked),
        "eligible_count": eligible_count,
        "selected_count": len(selected),
        "collision_report": collision_results,
        "hard_blocked": hard_blocked,
        "selected": [
            {
                "import_item_id": int(r["import_item_id"]),
                "lemma": r["lemma"],
                "correct_answer": r["correct_answer"],
                "concept_group": r.get("concept_group", ""),
                "collision_note": r["collision_note"],
                "distractors": [
                    r.get("distractor_1", ""),
                    r.get("distractor_2", ""),
                    r.get("distractor_3", ""),
                ],
            }
            for r in selected
        ],
        "unselected_eligible_reserve": [
            {
                "import_item_id": int(r["import_item_id"]),
                "lemma": r["lemma"],
                "concept_group": r.get("concept_group", ""),
                "collision_note": r["collision_note"],
            }
            for r in unselected_eligible
        ],
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def write_collision_report(pack: dict, output_dir: str) -> str:
    path = os.path.join(output_dir, "noun10k_tranche2_collision_report.json")
    out = {
        "prepared_at": pack["prepared_at"],
        "active_bank_size": pack["active_bank_size"],
        "active_noun10k_count": pack["active_noun10k_count"],
        "remaining_pool_size": pack["remaining_pool_size"],
        "hard_blocked_count": pack["hard_blocked_count"],
        "hard_blocked": pack["hard_blocked"],
        "eligible_count": pack["eligible_count"],
        "full_collision_results": pack["collision_report"],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return path


def write_manifest_json(pack: dict, output_dir: str) -> str:
    path = os.path.join(output_dir, "noun10k_tranche2_manifest.json")
    out = {
        "prepared_at": pack["prepared_at"],
        "activation_status": "PREPARE_ONLY — DO NOT ACTIVATE without monitoring gate",
        "selected_count": pack["selected_count"],
        "selected": pack["selected"],
        "unselected_eligible_reserve": pack["unselected_eligible_reserve"],
        "selection_rules_applied": [
            "prefer CLEAN collision_note over WARN",
            f"max {MAX_PER_CONCEPT_GROUP} items per concept_group per tranche",
            "exclude items with Rule 1b hard block against current active bank",
            "for intra-cluster WARN pairs among inactive items: include at most one side",
        ],
        "activation_gate": (
            "Do not run apply script until monitoring runner reports "
            "PREPARE_NEXT_TRANCHE verdict AND Rule 1 re-check passes."
        ),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return path


def write_manifest_csv(pack: dict, output_dir: str) -> str:
    path = os.path.join(output_dir, "noun10k_tranche2_manifest.csv")
    fields = [
        "import_item_id", "lemma", "correct_answer",
        "distractor_1", "distractor_2", "distractor_3",
        "concept_group", "collision_note", "selection_status",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        selected_ids = {r["import_item_id"] for r in pack["selected"]}
        for r in pack["selected"]:
            writer.writerow({
                "import_item_id": r["import_item_id"],
                "lemma": r["lemma"],
                "correct_answer": r["correct_answer"],
                "distractor_1": r["distractors"][0],
                "distractor_2": r["distractors"][1],
                "distractor_3": r["distractors"][2],
                "concept_group": r["concept_group"],
                "collision_note": r["collision_note"],
                "selection_status": "SELECTED",
            })
        for r in pack["unselected_eligible_reserve"]:
            writer.writerow({
                "import_item_id": r["import_item_id"],
                "lemma": r["lemma"],
                "correct_answer": "",
                "distractor_1": "",
                "distractor_2": "",
                "distractor_3": "",
                "concept_group": r["concept_group"],
                "collision_note": r["collision_note"],
                "selection_status": "RESERVE",
            })
    return path


def write_apply_script_donotrun(pack: dict, output_dir: str) -> str:
    path = os.path.join(output_dir, "noun10k_tranche2_apply_DONOTRUN.sh")
    selected = pack["selected"]
    item_ids = [str(r["import_item_id"]) for r in selected]
    ids_csv = ", ".join(item_ids)
    n = len(selected)
    prepared_at = pack["prepared_at"]

    lines = [
        "#!/usr/bin/env bash",
        "# ==============================================================================",
        "# DO NOT RUN -- PREPARE ONLY",
        "# ==============================================================================",
        "# Generated by noun10k_tranche2_prepare.py on " + prepared_at + ".",
        "# Activates noun/10K tranche 2 items in data/lingua_staging.db.",
        "#",
        "# ACTIVATION IS NOT AUTHORIZED until all of the following are true:",
        "#   1. noun10k_monitoring_runner.py verdict = PREPARE_NEXT_TRANCHE",
        "#      (minimum 30 sessions, >= 3 real users)",
        "#   2. At least one of T1-T4 has fired",
        "#   3. No active item with pct_correct < 20%",
        "#   4. Rule 1 anti-collision re-check against expanded active bank complete",
        "#",
        "# Usage (dry-run):",
        "#   bash diagnostics_exports/current/noun10k_tranche2_apply_DONOTRUN.sh",
        "# Usage (apply -- only when authorized):",
        "#   bash diagnostics_exports/current/noun10k_tranche2_apply_DONOTRUN.sh --apply",
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
        'echo "DO NOT RUN / PREPARE ONLY script for noun/10K tranche 2"',
        'echo "DB: $DB"',
        "",
        "# " + str(n) + " selected items:",
        'SELECTED_IDS="' + ids_csv + '"',
        "",
        'echo ""',
        'echo "Items that would be activated:"',
    ]

    for iid, r in zip(item_ids, selected):
        lines.append('echo "  ' + iid + "  " + r["lemma"] + '"')

    lines += [
        "",
        'echo ""',
        'echo "Pre-flight checks..."',
        "",
        "# Check: all items exist with is_active=0",
        'COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items'
        " WHERE id IN (" + ids_csv + ")"
        " AND pos='noun' AND bin_name='10K' AND is_active=0;\")",
        'if [ "$COUNT" -ne ' + str(n) + " ]; then",
        '  echo "FAIL: Expected ' + str(n) + ' inactive noun/10K items, found $COUNT"',
        "  exit 1",
        "fi",
        '  echo "  PASS: ' + str(n) + ' items found in DB with is_active=0"',
        "",
        "# Check: no active lemma duplicates",
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
        "# Rule 1a: new correct_answers not in active bank distractors",
        'R1A=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items vi_new'
        " JOIN vocab_choices vc ON vc.choice_text=vi_new.correct_answer"
        " JOIN vocab_items vi_act ON vi_act.id=vc.item_id"
        " WHERE vi_new.id IN (" + ids_csv + ")"
        ' AND vc.is_correct=0 AND vi_act.is_active=1;")',
        'if [ "$R1A" -ne 0 ]; then',
        '  echo "FAIL: Rule 1a -- $R1A new correct_answers in active distractors"',
        "  exit 1",
        "fi",
        '  echo "  PASS: Rule 1a"',
        "",
        "# Rule 1b: active correct_answers not in new item distractors",
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
        'echo ""',
        'if [ "$APPLY" -eq 0 ]; then',
        '  echo "DRY RUN -- no changes made."',
        '  echo "Re-run with --apply to activate ' + str(n) + ' items."',
        "  exit 0",
        "fi",
        "",
        'echo "Activating ' + str(n) + ' noun/10K tranche 2 items..."',
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
        'echo "Post-activation active noun/10K count:"',
        'sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE pos=\'noun\' AND bin_name=\'10K\' AND is_active=1;"',
        'echo "DONE -- tranche 2 activated."',
    ]

    script = "\n".join(lines) + "\n"

    with open(path, "w", encoding="utf-8") as f:
        f.write(script)
    os.chmod(path, 0o644)
    return path


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def print_summary(pack: dict) -> None:
    print("=" * 60)
    print("NOUN/10K TRANCHE 2 — PREPARE ONLY REPORT")
    print(f"Generated: {pack['prepared_at']}")
    print("STATUS: DO NOT ACTIVATE — prepare-only mode")
    print("=" * 60)
    print(f"\nActive bank: {pack['active_bank_size']} items total")
    print(f"Active noun/10K: {pack['active_noun10k_count']} items")
    print(f"\nPool: {pack['remaining_pool_size']} items remaining (is_active=0 in DB)")
    print(f"Hard blocked (Rule 1b against active bank): {pack['hard_blocked_count']}")
    print(f"Eligible for tranche 2: {pack['eligible_count']}")
    print(f"\nSelected for tranche 2 ({pack['selected_count']} items):")
    for r in pack["selected"]:
        print(f"  {r['import_item_id']}  {r['lemma']:<20} "
              f"ca={r['correct_answer']:<20} "
              f"cg={r['concept_group']:<30} "
              f"note={r['collision_note'][:40]}")
    if pack["hard_blocked"]:
        print(f"\nHard blocked items (not selectable without distractor fix):")
        for b in pack["hard_blocked"]:
            r1b = b["rule1b"]
            print(f"  {b['item_id']}  {b['lemma']:<20} "
                  f"reason={r1b['violations'][0] if r1b['violations'] else 'other'}")
    print(f"\nReserve pool (eligible but not selected, available for later tranches): "
          f"{len(pack['unselected_eligible_reserve'])} items")
    print(f"\nActivation gate: DO NOT RUN apply script until monitoring runner")
    print(f"  reports PREPARE_NEXT_TRANCHE AND minimum sample is met.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PREPARE ONLY: noun/10K tranche 2 preparation. No DB writes."
    )
    parser.add_argument("--db", default="data/lingua_staging.db")
    parser.add_argument("--csv", default=IMPORT_READY_CSV)
    parser.add_argument("--output-dir", default="diagnostics_exports/current/")
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"ERROR: DB not found: {args.db}", file=sys.stderr)
        return 1
    if not os.path.exists(args.csv):
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    try:
        pack = build_tranche2_pack(conn, args.csv)
    finally:
        conn.close()

    print_summary(pack)

    os.makedirs(args.output_dir, exist_ok=True)

    p1 = write_collision_report(pack, args.output_dir)
    p2 = write_manifest_json(pack, args.output_dir)
    p3 = write_manifest_csv(pack, args.output_dir)
    p4 = write_apply_script_donotrun(pack, args.output_dir)

    print(f"\nFiles written:")
    print(f"  {p1}")
    print(f"  {p2}")
    print(f"  {p3}")
    print(f"  {p4}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
