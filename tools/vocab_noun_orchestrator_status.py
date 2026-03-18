from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
ART = ROOT / "artifacts"
MANUAL = ROOT / "data/manual"

def latest(pattern: str):
    xs = sorted(ART.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return xs[0] if xs else None

def main() -> None:
    out = {
        "latest_reports": {
            "noun_remediation_report_v2": str(latest("noun_remediation_report_v2_*") or ""),
            "noun_bulk_prep_v4": str(latest("noun_bulk_prep_v4_*") or ""),
            "noun_apply_v5": str(latest("noun_remediation_apply_v5_*") or ""),
        },
        "manual_maps": sorted([p.name for p in MANUAL.glob("noun_manual_ru_map_v*.json")]),
        "next_blocker": "noun dispatcher/apply contract missing",
        "ready_for_autonomous_noun_loop": False,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
