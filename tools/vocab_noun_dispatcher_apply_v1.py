from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
ART = ROOT / "artifacts"

REPORT_V2 = ROOT / "tools/vocab_noun_remediation_report_v2.py"
BULK_PREP_V4 = ROOT / "tools/vocab_noun_bulk_prep_v4.py"
APPLY_V5 = ROOT / "tools/vocab_noun_remediation_apply_v5.py"
STATUS = ROOT / "tools/vocab_noun_orchestrator_status.py"
READINESS = ROOT / "tools/vocab_prod_readiness_report.py"
FORENSICS = ROOT / "tools/run_vocab_post_wiring_forensics.py"
MANUAL_MAP_V5 = ROOT / "data/manual/noun_manual_ru_map_v6.json"

def latest_dir(prefix: str) -> Path | None:
    matches = sorted(ART.glob(f"{prefix}_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None

def run_tool(args: list[str]) -> dict:
    proc = subprocess.run(args, capture_output=True, text=True, check=True)
    return {
        "tool": " ".join(args[1:]),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "returncode": proc.returncode,
    }

def main() -> None:
    outdir = ART / f"noun_dispatcher_apply_v1_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)

    runs = []

    runs.append(run_tool([sys.executable, str(REPORT_V2)]))
    report_dir = latest_dir("noun_remediation_report_v2")
    report_json = report_dir / "top400_needs_manual_ru_v2.json"

    runs.append(run_tool([sys.executable, str(BULK_PREP_V4), "--source-report", str(report_json)]))
    bulk_dir = latest_dir("noun_bulk_prep_v4")
    shortlist_json = bulk_dir / "safe_shortlist_v4.json"

    runs.append(run_tool([
        sys.executable, str(APPLY_V5),
        "--shortlist-source", str(shortlist_json),
        "--manual-map", str(MANUAL_MAP_V5),
    ]))
    apply_dir = latest_dir("noun_remediation_apply_v5")

    runs.append(run_tool([sys.executable, str(STATUS)]))
    runs.append(run_tool([sys.executable, str(READINESS)]))
    runs.append(run_tool([sys.executable, str(FORENSICS)]))

    report = {
        "mode": "noun_dispatcher_apply_v1",
        "fresh_chain": {
            "noun_remediation_report_v2": str(report_dir) if report_dir else None,
            "noun_bulk_prep_v4": str(bulk_dir) if bulk_dir else None,
            "noun_remediation_apply_v5": str(apply_dir) if apply_dir else None,
        },
        "explicit_inputs": {
            "report_json": str(report_json),
            "shortlist_json": str(shortlist_json),
            "manual_map": str(MANUAL_MAP_V5),
        },
        "tool_runs": runs,
        "notes": [
            "dispatcher v1 now passes explicit artifact paths into noun subtools",
            "noun loop remains semi-automatic because manual_ru_map is still required",
            "full autonomy starts only after map generation ceases to need human review"
        ],
    }

    (outdir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
