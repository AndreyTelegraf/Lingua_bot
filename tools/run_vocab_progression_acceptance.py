from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import json
import sqlite3
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT = ROOT / "artifacts" / "vocab_progression_acceptance_20260317"
OUT.mkdir(parents=True, exist_ok=True)

from services.vocab_runtime.attempt_coverage import get_attempt_coverage_snapshot  # type: ignore
from services.vocab_runtime.progression_export import build_vocab_progression_export  # type: ignore


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        """
        SELECT id
        FROM vocab_attempts
        WHERE status = 'finished'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    if not row:
        raise SystemExit("no finished vocab attempt found")

    attempt_id = int(row["id"])
    export = build_vocab_progression_export(conn, attempt_id=attempt_id)
    coverage = get_attempt_coverage_snapshot(conn, attempt_id=attempt_id, total_questions=24)

    profile = export["profile"]
    acceptance = {
        "attempt_id": attempt_id,
        "checks": {
            "has_lexical_baseline": bool(profile.get("lexical_baseline")),
            "has_lexical_profile": bool(profile.get("lexical_profile")),
            "has_progression_ready_hints": bool(profile.get("progression_ready_hints")),
            "has_signal_quality": bool(profile.get("signal_quality")),
            "has_attempt_coverage_snapshot": bool(coverage),
            "export_mode_is_vocab": export.get("mode") == "vocab",
            "export_spec_version_ok": export.get("spec_version") == "progression_export_v1",
        },
        "coverage_priority_order": coverage.get("priority_order", []),
        "recommended_lesson_packs": profile.get("progression_ready_hints", {}).get("recommended_lesson_packs", []),
        "recommended_game_packs": profile.get("progression_ready_hints", {}).get("recommended_game_packs", []),
    }

    (OUT / "summary.json").write_text(
        json.dumps(acceptance, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(acceptance, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
