from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
ART = ROOT / "artifacts"
MANUAL = ROOT / "data/manual"
TOOLS = ROOT / "tools"

def latest(prefix: str) -> str | None:
    matches = sorted(ART.glob(f"{prefix}_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return str(matches[0]) if matches else None

def main() -> None:
    dispatcher_exists = (TOOLS / "vocab_noun_dispatcher_apply_v1.py").exists()
    manual_maps = sorted(p.name for p in MANUAL.glob("noun_manual_ru_map_v*.json"))

    latest_reports = {
        "noun_remediation_report_v2": latest("noun_remediation_report_v2"),
        "noun_bulk_prep_v4": latest("noun_bulk_prep_v4"),
        "noun_apply_v5": latest("noun_remediation_apply_v5"),
        "noun_dispatcher_apply_v1": latest("noun_dispatcher_apply_v1"),
    }

    shortlist_exists = latest_reports["noun_bulk_prep_v4"] is not None
    dispatcher_ran = latest_reports["noun_dispatcher_apply_v1"] is not None

    if not dispatcher_exists:
        next_blocker = "noun dispatcher/apply contract missing"
        ready = False
    elif shortlist_exists:
        next_blocker = "manual_ru_map remains gating layer"
        ready = False
    else:
        next_blocker = "safe shortlist exhausted; next scale layer requires new noun sourcing/remediation strategy"
        ready = False

    report = {
        "latest_reports": latest_reports,
        "manual_maps": manual_maps,
        "dispatcher_exists": dispatcher_exists,
        "dispatcher_ran": dispatcher_ran,
        "next_blocker": next_blocker,
        "ready_for_autonomous_noun_loop": ready,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
