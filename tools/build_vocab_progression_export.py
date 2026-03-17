from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DB = ROOT / "data/lingua_staging.db"
OUT = ROOT / "artifacts" / "vocab_progression_export_20260317"
OUT.mkdir(parents=True, exist_ok=True)

from services.vocab_runtime.progression_export import build_vocab_progression_export


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

    (OUT / "export.json").write_text(
        json.dumps(export, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT / "summary.json").write_text(
        json.dumps(
            {
                "attempt_id": attempt_id,
                "spec_version": export["spec_version"],
                "path": str(OUT / "export.json"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"attempt_id": attempt_id, "path": str(OUT / "export.json")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
