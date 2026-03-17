from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from services.vocab_runtime.attempt_coverage import get_attempt_coverage_snapshot

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT = ROOT / "artifacts" / f"vocab_attempt_coverage_snapshot_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
OUT.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

attempt_row = conn.execute(
    '''
    SELECT id
    FROM vocab_attempts
    WHERE finished_at IS NOT NULL
    ORDER BY id DESC
    LIMIT 1
    '''
).fetchone()

if attempt_row is None:
    raise SystemExit("No finished vocab attempt found")

attempt_id = int(attempt_row["id"] if not isinstance(attempt_row, tuple) else attempt_row[0])
snapshot = get_attempt_coverage_snapshot(conn, attempt_id=attempt_id, total_questions=24)

summary = {
    "db": str(DB),
    "attempt_id": attempt_id,
    "snapshot": snapshot,
}
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
print(OUT / "summary.json")

conn.close()
