#!/usr/bin/env python3
"""
adverb_5k_rebuild_preapply_audit.py
Stage 1 — Pre-apply safety audit. Read-only.

Verifies:
  1. DB path matches manifest
  2. Target item IDs match manifest exactly
  3. All 6 items are pos='adverb', bin_name='5K', is_active=0 in live DB
  4. Apply script touches only vocab_choices for the 6 approved items
  5. Apply script contains no is_active writes
  6. Apply script contains no writes to vocab_items, selector, runtime, noun, verb tables
  7. Stage 3 validation was accepted (apply_gate satisfied)

Output:
  diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_preapply_audit.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
MANIFEST_PATH = "diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_manifest.json"
VALIDATION_PATH = "diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_validation.json"
APPLY_SCRIPT_PATH = "scripts/adverb_5k_rebuild_apply_DONOTRUN.sh"
OUTPUT_DIR = "diagnostics_exports/adverb_5k_rebuild/current"

EXPECTED_ITEM_IDS = {3958, 3960, 10017, 3963, 10019, 3970}
FORBIDDEN_TABLE_PATTERNS = [
    r"\bvocab_items\b",
    r"\bis_active\s*=",
    r"\bselector",
    r"\bruntime",
    r"\bsession",
    r"\buser_",
    r"UPDATE\s+vocab_choices\s+SET",
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Pre-apply safety audit. Read-only.")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--manifest", default=MANIFEST_PATH)
    ap.add_argument("--validation", default=VALIDATION_PATH)
    ap.add_argument("--apply-script", default=APPLY_SCRIPT_PATH)
    ap.add_argument("--output-dir", default=OUTPUT_DIR)
    args = ap.parse_args(argv)

    checks: dict[str, dict] = {}
    all_pass = True

    # --- Check 1: files exist ---
    for label, path in [
        ("manifest_exists", args.manifest),
        ("validation_exists", args.validation),
        ("apply_script_exists", args.apply_script),
        ("db_exists", args.db),
    ]:
        ok = os.path.exists(path)
        checks[label] = {"pass": ok, "detail": path if ok else f"NOT FOUND: {path}"}
        if not ok:
            all_pass = False

    if not all(checks[k]["pass"] for k in ["manifest_exists", "validation_exists", "apply_script_exists", "db_exists"]):
        _write_report(args.output_dir, checks, all_pass=False)
        print("STAGE 1 ACCEPTANCE: FAIL — required files missing")
        return 1

    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(args.validation, encoding="utf-8") as f:
        validation = json.load(f)
    with open(args.apply_script, encoding="utf-8") as f:
        script_text = f.read()

    # --- Check 2: DB path matches manifest ---
    manifest_db = manifest.get("db", "")
    db_match = manifest_db == args.db
    checks["db_path_matches_manifest"] = {
        "pass": db_match,
        "detail": f"manifest.db={manifest_db!r}, arg.db={args.db!r}",
    }
    if not db_match:
        all_pass = False

    # --- Check 3: stage3 validation accepted ---
    stage3_accepted = validation.get("stage3_accept", False)
    checks["stage3_accepted"] = {
        "pass": stage3_accepted,
        "detail": "stage3_accept=True" if stage3_accepted else "stage3_accept is not True",
    }
    if not stage3_accepted:
        all_pass = False

    # --- Check 4: manifest item IDs match expected set ---
    manifest_ids = {op["item_id"] for op in manifest.get("operations", [])}
    ids_match = manifest_ids == EXPECTED_ITEM_IDS
    checks["manifest_ids_match_expected"] = {
        "pass": ids_match,
        "detail": f"manifest={sorted(manifest_ids)}, expected={sorted(EXPECTED_ITEM_IDS)}",
    }
    if not ids_match:
        all_pass = False

    # --- Check 5: live DB item state ---
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    live_items = {}
    for item_id in EXPECTED_ITEM_IDS:
        row = conn.execute(
            "SELECT id, lemma, bin_name, pos, is_active FROM vocab_items WHERE id=?",
            (item_id,)
        ).fetchone()
        live_items[item_id] = dict(row) if row else None
    conn.close()

    item_state_errors = []
    for item_id, row in live_items.items():
        if row is None:
            item_state_errors.append(f"id={item_id}: NOT FOUND in DB")
        else:
            if row["pos"] != "adverb":
                item_state_errors.append(f"id={item_id}: pos={row['pos']!r}")
            if row["bin_name"] != "5K":
                item_state_errors.append(f"id={item_id}: bin_name={row['bin_name']!r}")
            if row["is_active"] != 0:
                item_state_errors.append(f"id={item_id}: is_active={row['is_active']} (ACTIVE!)")

    checks["live_db_item_state"] = {
        "pass": len(item_state_errors) == 0,
        "detail": "all 6 items confirmed pos=adverb, bin=5K, is_active=0" if not item_state_errors
                  else "; ".join(item_state_errors),
    }
    if item_state_errors:
        all_pass = False

    # --- Check 6: apply script only touches vocab_choices ---
    # Extract all SQL statements from the script
    sql_in_script = re.findall(r'sqlite3[^"]*"([^"]+)"', script_text)
    tables_touched = set()
    non_vc_writes = []
    for sql in sql_in_script:
        sql_upper = sql.upper().strip()
        if sql_upper.startswith("DELETE FROM"):
            m = re.search(r"DELETE FROM\s+(\w+)", sql_upper)
            if m:
                tables_touched.add(m.group(1))
                if m.group(1) != "VOCAB_CHOICES":
                    non_vc_writes.append(f"DELETE FROM {m.group(1)}")
        elif sql_upper.startswith("INSERT INTO"):
            m = re.search(r"INSERT INTO\s+(\w+)", sql_upper)
            if m:
                tables_touched.add(m.group(1))
                if m.group(1) != "VOCAB_CHOICES":
                    non_vc_writes.append(f"INSERT INTO {m.group(1)}")
        elif sql_upper.startswith("UPDATE"):
            m = re.search(r"UPDATE\s+(\w+)", sql_upper)
            if m:
                tables_touched.add(m.group(1))
                non_vc_writes.append(f"UPDATE {m.group(1)}")

    checks["script_only_touches_vocab_choices"] = {
        "pass": len(non_vc_writes) == 0,
        "detail": f"tables in SQL: {sorted(tables_touched)}" + (
            f"; non-vocab_choices writes: {non_vc_writes}" if non_vc_writes else ""
        ),
    }
    if non_vc_writes:
        all_pass = False

    # --- Check 7: script item IDs match expected ---
    script_item_ids = set(int(m) for m in re.findall(r"WHERE item_id=(\d+)", script_text))
    # Also from INSERT VALUES
    script_item_ids |= set(int(m) for m in re.findall(r"VALUES \((\d+),", script_text))
    script_ids_match = script_item_ids == EXPECTED_ITEM_IDS
    checks["script_item_ids_match_expected"] = {
        "pass": script_ids_match,
        "detail": f"script={sorted(script_item_ids)}, expected={sorted(EXPECTED_ITEM_IDS)}",
    }
    if not script_ids_match:
        all_pass = False

    # --- Check 8: no is_active writes in script ---
    has_is_active_write = bool(re.search(r"is_active\s*=", script_text, re.IGNORECASE))
    checks["no_is_active_writes"] = {
        "pass": not has_is_active_write,
        "detail": "no is_active assignments found" if not has_is_active_write
                  else "FOUND is_active= in script",
    }
    if has_is_active_write:
        all_pass = False

    # --- Check 9: no forbidden table/pattern references ---
    forbidden_found = []
    for pattern in FORBIDDEN_TABLE_PATTERNS:
        if re.search(pattern, script_text, re.IGNORECASE):
            if pattern not in [r"\bis_active\s*="]:  # already covered above
                forbidden_found.append(pattern)
    checks["no_forbidden_patterns"] = {
        "pass": len(forbidden_found) == 0,
        "detail": "no forbidden patterns" if not forbidden_found
                  else f"found: {forbidden_found}",
    }
    if forbidden_found:
        all_pass = False

    # --- Check 10: manifest delete+insert counts match expected ---
    expected_deletes = 6 * 6  # 6 items, 6 old choices each
    expected_inserts = 6 * 4  # 6 items, 4 new choices each
    counts_ok = (manifest["total_deletes"] == expected_deletes and
                 manifest["total_inserts"] == expected_inserts)
    checks["manifest_counts_correct"] = {
        "pass": counts_ok,
        "detail": f"deletes={manifest['total_deletes']} (expected {expected_deletes}), "
                  f"inserts={manifest['total_inserts']} (expected {expected_inserts})",
    }
    if not counts_ok:
        all_pass = False

    _write_report(args.output_dir, checks, all_pass, live_items)

    print("STAGE 1 — PRE-APPLY SAFETY AUDIT")
    for name, result in checks.items():
        status = "PASS" if result["pass"] else "FAIL"
        print(f"  [{status}] {name}: {result['detail']}")
    print()
    if all_pass:
        print("  SAFE TO PROCEED: YES")
        print("STAGE 1 ACCEPTANCE: PASS")
        return 0
    else:
        print("  SAFE TO PROCEED: NO")
        print("STAGE 1 ACCEPTANCE: FAIL")
        return 1


def _write_report(output_dir: str, checks: dict, all_pass: bool, live_items: dict | None = None) -> None:
    lines = [
        "# Adverb 5K Rebuild — Pre-Apply Safety Audit",
        "",
        "## Result",
        "",
        f"**SAFE TO PROCEED: {'YES' if all_pass else 'NO'}**",
        "",
        "## Checks",
        "",
        "| Check | Result | Detail |",
        "|-------|--------|--------|",
    ]
    for name, result in checks.items():
        status = "✓ PASS" if result["pass"] else "✗ FAIL"
        lines.append(f"| {name} | {status} | {result['detail']} |")

    if live_items:
        lines += [
            "",
            "## Live DB Item State",
            "",
            "| item_id | lemma | bin | pos | is_active |",
            "|---------|-------|-----|-----|-----------|",
        ]
        for item_id, row in sorted(live_items.items()):
            if row:
                lines.append(f"| {item_id} | {row['lemma']} | {row['bin_name']} | {row['pos']} | {row['is_active']} |")
            else:
                lines.append(f"| {item_id} | NOT FOUND | — | — | — |")

    lines += [
        "",
        "## Write Scope",
        "",
        "- Table: `vocab_choices` only",
        "- Item IDs: 3958, 3960, 10017, 3963, 10019, 3970",
        "- No writes to `vocab_items`",
        "- No `is_active` changes",
        "- No selector/runtime/noun/verb mutations",
    ]

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "adverb_5k_rebuild_preapply_audit.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Audit: {path}")


if __name__ == "__main__":
    sys.exit(main())
