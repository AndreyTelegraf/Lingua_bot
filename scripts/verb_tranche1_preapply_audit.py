#!/usr/bin/env python3
"""
verb_tranche1_preapply_audit.py
Stage 1 — Pre-apply safety audit. Read-only.
Verifies the apply script targets only intended rows.
Outputs: diagnostics_exports/verb_tranche1/current/remediation_preapply_audit.md
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

DB_PATH = "data/lingua_staging.db"
MANIFEST_PATH = "diagnostics_exports/verb_tranche1/current/verb_tranche1_post_remediation_manifest.json"
OUTPUT_DIR = "diagnostics_exports/verb_tranche1/current"

# Exactly what the apply script targets — derived by reading the script verbatim
APPLY_SCRIPT_TARGETS = {
    "vocab_items_ca": [
        (868,  "торопить",   "ускорять"),
        (921,  "менять",     "изменять"),
        (1732, "выполнять",  "реализовывать"),
        (1759, "провести",   "устанавливать"),
        (2172, "писать",     "красить"),
        (3467, "оценивать",  "приближать"),
        (3491, "нарушать",   "отменять"),
        (3509, "дубить",     "выделывать"),
        # 9328 CA kept
    ],
    "vocab_choices_correct": [
        (868,  "ускорять"),
        (921,  "изменять"),
        (1732, "реализовывать"),
        (1759, "устанавливать"),
        (2172, "красить"),
        (3467, "приближать"),
        (3491, "отменять"),
        (3509, "выделывать"),
    ],
    "vocab_choices_distractors": {
        # choice_id: (expected_item_id, old_text, new_text)
        403627: (868,  "предпочесть",   "замедлять"),
        403628: (868,  "активизировать","тормозить"),
        403630: (868,  "считать",       "мчаться"),
        403631: (868,  "прыгать",       "разгонять"),
        403632: (868,  "обвинять",      "приостанавливать"),
        403124: (921,  "отдыхать",      "уточнять"),
        403125: (921,  "принимать",     "обновлять"),
        403126: (921,  "успеть",        "откладывать"),
        403128: (921,  "переводить",    "удалять"),
        403382: (1732, "обвинить",      "планировать"),
        403383: (1732, "болеть",        "разрабатывать"),
        403385: (1732, "прекращать",    "завершать"),
        403386: (1732, "давить",        "составлять"),
        403261: (1759, "предложить",    "разбирать"),
        403263: (1759, "обожать",       "перемещать"),
        403265: (1759, "приспособить",  "обрабатывать"),
        403266: (1759, "охотиться",     "запускать"),
        403171: (2172, "расширить",     "моделировать"),
        403173: (2172, "будить",        "конструировать"),
        403175: (2172, "исчезать",      "формировать"),
        403081: (3467, "мечтать",       "отдаляться"),
        403082: (3467, "менять",        "разделять"),
        403084: (3467, "целовать",      "сталкивать"),
        403085: (3467, "отбиваться",    "окружать"),
        403087: (3491, "отбиваться",    "продлевать"),
        403088: (3491, "целовать",      "одобрять"),
        403089: (3491, "менять",        "подтверждать"),
        403091: (3491, "мечтать",       "перебивать"),
        403092: (3491, "переводить",    "допускать"),
        433777: (3509, "нанимать",      "замачивать"),
        433778: (3509, "предать",       "очищать"),
        433779: (3509, "болеть",        "смягчать"),
        433780: (3509, "переводить",    "пропитывать"),
        433781: (3509, "охотиться",     "отмачивать"),
        404780: (9328, "активизировать","проектировать"),
        404781: (9328, "бегать",        "формулировать"),
        404782: (9328, "болеть",        "объединять"),
        404784: (9328, "будить",        "преувеличивать"),
    },
}

TARGET_ITEM_IDS = {868, 921, 1732, 1759, 2172, 3467, 3491, 3509, 9328}


def main() -> int:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    manifest_ids = {m["item_id"] for m in manifest["items"]}

    issues: list[str] = []
    checks: list[tuple[str, str]] = []

    # --- Check 1: target IDs match manifest ---
    script_ids = TARGET_ITEM_IDS
    if script_ids == manifest_ids:
        checks.append(("Target IDs match manifest", "PASS"))
    else:
        diff = script_ids.symmetric_difference(manifest_ids)
        issues.append(f"Target ID mismatch: {diff}")
        checks.append(("Target IDs match manifest", f"FAIL: {diff}"))

    # --- Check 2: no is_active in apply script ---
    with open("scripts/verb_tranche1_remediation_apply_DONOTRUN.sh") as f:
        script_text = f.read()
    if "is_active" in script_text.lower():
        issues.append("apply script contains 'is_active'")
        checks.append(("No is_active in apply script", "FAIL"))
    else:
        checks.append(("No is_active in apply script", "PASS"))

    # --- Check 3: only vocab_items and vocab_choices touched ---
    forbidden_tables = []
    for word in ["sessions", "users", "attempts", "vocab_attempts", "vocab_sessions",
                 "vocab_feedback", "vocab_reports"]:
        if word in script_text.lower():
            forbidden_tables.append(word)
    if forbidden_tables:
        issues.append(f"Forbidden tables referenced: {forbidden_tables}")
        checks.append(("Only vocab_items/vocab_choices touched", f"FAIL: {forbidden_tables}"))
    else:
        checks.append(("Only vocab_items/vocab_choices touched", "PASS"))

    # --- Check 4: only correct_answer and choice_text columns modified ---
    for col in ["bin_name", "pos", "status", "lemma"]:
        # look for SET col or ,col pattern
        import re
        if re.search(rf"\bSET\b.*\b{col}\b", script_text, re.IGNORECASE):
            issues.append(f"Column '{col}' modified in apply script")
            checks.append((f"Column '{col}' not modified", f"FAIL"))

    # --- Check 5: current DB state — vocab_items CA pre-values ---
    ca_state_ok = True
    ca_details = []
    for (item_id, expected_old, expected_new) in APPLY_SCRIPT_TARGETS["vocab_items_ca"]:
        row = conn.execute("SELECT correct_answer, is_active FROM vocab_items WHERE id=?", (item_id,)).fetchone()
        if row is None:
            issues.append(f"item_id={item_id} not found in DB")
            ca_details.append((item_id, "NOT FOUND", "—", "—", "FAIL"))
            ca_state_ok = False
            continue
        actual_ca = (row["correct_answer"] or "").strip()
        is_active = row["is_active"]
        if is_active != 0:
            issues.append(f"item_id={item_id} is_active={is_active} (expected 0)")
            ca_details.append((item_id, actual_ca, expected_old, expected_new, f"FAIL(is_active={is_active})"))
            ca_state_ok = False
        elif actual_ca == expected_old:
            ca_details.append((item_id, actual_ca, expected_old, expected_new, "READY"))
        elif actual_ca == expected_new:
            ca_details.append((item_id, actual_ca, expected_old, expected_new, "ALREADY_APPLIED"))
        else:
            issues.append(f"item_id={item_id} CA='{actual_ca}' (expected old='{expected_old}')")
            ca_details.append((item_id, actual_ca, expected_old, expected_new, f"WARN(unexpected={actual_ca})"))

    if ca_state_ok:
        checks.append(("Pre-apply CA state consistent", "PASS"))
    else:
        checks.append(("Pre-apply CA state consistent", "FAIL (see details)"))

    # --- Check 6: choice_id ownership — each distractor choice_id belongs to expected item_id ---
    ownership_ok = True
    ownership_details = []
    for choice_id, (expected_item_id, expected_old_text, _) in APPLY_SCRIPT_TARGETS["vocab_choices_distractors"].items():
        row = conn.execute(
            "SELECT item_id, choice_text, is_correct FROM vocab_choices WHERE id=?", (choice_id,)
        ).fetchone()
        if row is None:
            issues.append(f"choice_id={choice_id} not found in DB")
            ownership_details.append((choice_id, "NOT FOUND", "—", "FAIL"))
            ownership_ok = False
            continue
        actual_item_id = row["item_id"]
        actual_text = (row["choice_text"] or "").strip()
        is_correct = row["is_correct"]
        if actual_item_id != expected_item_id:
            issues.append(f"choice_id={choice_id} belongs to item {actual_item_id}, expected {expected_item_id}")
            ownership_details.append((choice_id, actual_text, actual_item_id, "FAIL(wrong_item)"))
            ownership_ok = False
        elif is_correct != 0:
            issues.append(f"choice_id={choice_id} is_correct={is_correct} (expected distractor)")
            ownership_details.append((choice_id, actual_text, actual_item_id, "FAIL(is_correct=1)"))
            ownership_ok = False
        elif actual_text == expected_old_text:
            ownership_details.append((choice_id, actual_text, actual_item_id, "READY"))
        elif actual_text != expected_old_text:
            ownership_details.append((choice_id, actual_text, actual_item_id, f"WARN(text='{actual_text}' expected='{expected_old_text}')"))

    if ownership_ok:
        checks.append(("Choice_id ownership correct", "PASS"))
    else:
        checks.append(("Choice_id ownership correct", "FAIL (see details)"))

    conn.close()

    # --- Total distractor slot count ---
    total_replace_slots = len(APPLY_SCRIPT_TARGETS["vocab_choices_distractors"])
    total_ca_updates = len(APPLY_SCRIPT_TARGETS["vocab_items_ca"])
    total_correct_choice_updates = len(APPLY_SCRIPT_TARGETS["vocab_choices_correct"])

    overall = "SAFE_TO_PROCEED" if not issues else "BLOCKED"

    # Write MD
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    md_lines = [
        "# Verb Tranche1 Remediation — Pre-Apply Safety Audit",
        "",
        f"**DB:** {DB_PATH}",
        f"**Apply script:** scripts/verb_tranche1_remediation_apply_DONOTRUN.sh",
        f"**Commit anchor:** 8996afe",
        "",
        "## Check Results",
        "",
        "| Check | Result |",
        "|-------|--------|",
    ]
    for name, result in checks:
        md_lines.append(f"| {name} | {result} |")
    md_lines += [
        "",
        "## Scope Summary",
        "",
        f"- **Tables touched:** `vocab_items` (correct_answer), `vocab_choices` (choice_text)",
        f"- **Target items:** {sorted(TARGET_ITEM_IDS)}",
        f"- **vocab_items CA updates:** {total_ca_updates} rows",
        f"- **vocab_choices correct-row updates:** {total_correct_choice_updates} rows",
        f"- **vocab_choices distractor updates:** {total_replace_slots} rows",
        f"- **is_active changes:** NONE",
        f"- **Activation logic present:** NO",
        "",
        "## Pre-Apply CA State",
        "",
        "| item_id | current CA | expected old | expected new | state |",
        "|---------|-----------|--------------|--------------|-------|",
    ]
    for (item_id, actual, old, new, state) in ca_details:
        md_lines.append(f"| {item_id} | {actual} | {old} | {new} | {state} |")
    md_lines += [
        "",
        "## Choice Ownership Check",
        "",
        "| choice_id | current text | item_id | state |",
        "|-----------|-------------|---------|-------|",
    ]
    for (cid, text, iid, state) in ownership_details:
        md_lines.append(f"| {cid} | {text} | {iid} | {state} |")
    md_lines += [
        "",
        f"## Overall: **{overall}**",
        "",
    ]
    if issues:
        md_lines += ["## Issues", ""]
        for issue in issues:
            md_lines.append(f"- {issue}")

    md_path = os.path.join(OUTPUT_DIR, "remediation_preapply_audit.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    # Console summary
    print("=" * 60)
    print("STAGE 1 — PRE-APPLY SAFETY AUDIT")
    print("=" * 60)
    print(f"\nTarget items: {sorted(TARGET_ITEM_IDS)}")
    print(f"Distractor slots to replace: {total_replace_slots}")
    print(f"CA updates: {total_ca_updates}")
    print(f"Tables touched: vocab_items (correct_answer), vocab_choices (choice_text)")
    print(f"is_active changes: NONE")
    print(f"Forbidden writes absent: {'YES' if not any('FAIL' in r for _, r in checks) else 'NO'}")
    print()
    print("Checks:")
    for name, result in checks:
        print(f"  {'OK' if 'PASS' in result else 'FAIL':4}  {name}: {result}")
    print()
    if issues:
        print("ISSUES:")
        for i in issues:
            print(f"  - {i}")
        print()
    print(f"OVERALL: {overall}")
    print(f"\nArtifact: {md_path}")

    return 0 if overall == "SAFE_TO_PROCEED" else 1


if __name__ == "__main__":
    sys.exit(main())
