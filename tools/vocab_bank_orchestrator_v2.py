from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
ART = ROOT / "artifacts"

TOOLS = {
    "dryrun_report": ROOT / "tools/vocab_bank_orchestrator_dryrun.py",
    "apply_safe_core": ROOT / "tools/vocab_bank_orchestrator_apply_v1.py",
    "apply_adverb_followup": ROOT / "tools/vocab_adverb_followup_apply_v1.py",
    "apply_verb_remediation": ROOT / "tools/vocab_verb_remediation_apply_v1.py",
    "apply_noun_dispatcher": ROOT / "tools/vocab_noun_dispatcher_apply_v1.py",
    "prod_readiness": ROOT / "tools/vocab_prod_readiness_report.py",
}

def run_py(path: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    stdout = proc.stdout.strip()
    lines = [x for x in stdout.splitlines() if x.strip()]
    json_obj = None
    for line in reversed(lines):
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            json_obj = json.loads(s)
            break
    return {
        "tool": str(path),
        "stdout": stdout,
        "parsed_json": json_obj,
    }

def active_by_pos(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT pos, COUNT(*)
        FROM vocab_items
        WHERE is_active = 1
        GROUP BY pos
        ORDER BY pos
        """
    ).fetchall()
    return {str(r[0]): int(r[1]) for r in rows}

def structural_status(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT
          SUM(CASE WHEN choice_cnt = 0 THEN 1 ELSE 0 END) AS active_zero_choices,
          SUM(CASE WHEN choice_cnt != 6 THEN 1 ELSE 0 END) AS active_not_6_choices,
          SUM(CASE WHEN correct_cnt != 1 THEN 1 ELSE 0 END) AS active_not_1_correct,
          SUM(CASE WHEN distinct_cnt != 6 THEN 1 ELSE 0 END) AS active_not_6_distinct_choices
        FROM (
          SELECT
            vi.id,
            COUNT(vc.id) AS choice_cnt,
            SUM(CASE WHEN vc.is_correct = 1 THEN 1 ELSE 0 END) AS correct_cnt,
            COUNT(DISTINCT vc.choice_text) AS distinct_cnt
          FROM vocab_items vi
          LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
          WHERE vi.is_active = 1
          GROUP BY vi.id
        )
        """
    ).fetchone()
    return {
        "active_zero_choices": int(row[0] or 0),
        "active_not_6_choices": int(row[1] or 0),
        "active_not_1_correct": int(row[2] or 0),
        "active_not_6_distinct_choices": int(row[3] or 0),
    }

def duplicate_active_lemma_pos_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM (
          SELECT lower(trim(lemma)) AS lemma_norm, pos, COUNT(*) AS cnt
          FROM vocab_items
          WHERE is_active = 1
          GROUP BY lower(trim(lemma)), pos
          HAVING COUNT(*) > 1
        )
        """
    ).fetchone()
    return int(row[0] or 0)

def snapshot_state() -> dict:
    conn = sqlite3.connect(DB)
    try:
        return {
            "active_by_pos": active_by_pos(conn),
            "structural_status": structural_status(conn),
            "duplicate_active_lemma_pos_count": duplicate_active_lemma_pos_count(conn),
        }
    finally:
        conn.close()

def dryrun() -> dict:
    return {
        "mode": "dryrun",
        "state": snapshot_state(),
        "notes": [
            "dispatcher mode only; no db mutations",
            "safe verb/adverb layers already mostly exhausted",
            "noun dispatcher is wired, but manual_ru_map remains the main blocker toward 8000+",
        ],
    }

def apply_once() -> dict:
    before = snapshot_state()
    tool_runs = []

    for key in ["apply_safe_core", "apply_adverb_followup", "apply_verb_remediation", "apply_noun_dispatcher"]:
        path = TOOLS[key]
        if path.exists():
            tool_runs.append(run_py(path))
        else:
            tool_runs.append({
                "tool": str(path),
                "stdout": "",
                "parsed_json": None,
                "missing": True,
            })

    after = snapshot_state()
    return {
        "mode": "apply",
        "before": before,
        "after": after,
        "tool_runs": tool_runs,
    }

def loop(max_cycles: int) -> dict:
    cycles = []
    prev = snapshot_state()

    for i in range(1, max_cycles + 1):
        applied = apply_once()
        current = applied["after"]

        changed = current["active_by_pos"] != prev["active_by_pos"]
        cycles.append({
            "cycle": i,
            "before": applied["before"],
            "after": applied["after"],
            "changed": changed,
        })

        prev = current
        if not changed:
            cycles.append({
                "cycle": i,
                "status": "stopped_no_change",
                "reason": "existing proven apply tools made no further progress",
            })
            break

    return {
        "mode": "loop",
        "max_cycles": max_cycles,
        "cycles": cycles,
        "final_state": snapshot_state(),
        "notes": [
            "When loop converges with no change, next required layer is additional manual noun mapping.",
        ],
    }

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dryrun", "apply", "loop"], required=True)
    ap.add_argument("--max-cycles", type=int, default=10)
    args = ap.parse_args()

    ts = time.strftime("%Y%m%d_%H%M%S")
    outdir = ART / ("vocab_bank_orchestrator_v2_" + args.mode + "_" + ts)
    outdir.mkdir(parents=True, exist_ok=True)

    if args.mode == "dryrun":
        result = dryrun()
    elif args.mode == "apply":
        result = apply_once()
    else:
        result = loop(args.max_cycles)

    (outdir / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
