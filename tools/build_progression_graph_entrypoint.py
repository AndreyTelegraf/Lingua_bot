from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DB = ROOT / "data/lingua_staging.db"
OUT = ROOT / "artifacts" / "progression_graph_entrypoint_20260317"
OUT.mkdir(parents=True, exist_ok=True)

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
    vocab_export = build_vocab_progression_export(conn, attempt_id=attempt_id)

    graph_payload = {
        "graph_spec_version": "progression_graph_v1",
        "sources": {
            "vocab": vocab_export,
        },
        "notes": [
            "Only vocab source is wired in this layer.",
            "Level and CIPLE can be plugged into the same sources envelope later.",
        ],
    }

    (OUT / "entrypoint.json").write_text(
        json.dumps(graph_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT / "summary.json").write_text(
        json.dumps(
            {
                "attempt_id": attempt_id,
                "graph_spec_version": "progression_graph_v1",
                "source_modes": ["vocab"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"attempt_id": attempt_id, "source_modes": ["vocab"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
