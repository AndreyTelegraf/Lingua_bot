from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.vocab_runtime.attempt_coverage import (
    coverage_soft_bias_weights,
    get_attempt_coverage_snapshot,
)

DB = ROOT / "data" / "lingua_staging.db"
OUT = ROOT / "artifacts" / f"vocab_soft_bias_shadow_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
OUT.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

row = conn.execute(
    '''
    SELECT id
    FROM vocab_attempts
    WHERE status = 'finished'
    ORDER BY id DESC
    LIMIT 1
    '''
).fetchone()

if not row:
    raise SystemExit("no finished vocab attempts found")

attempt_id = int(row["id"])
snapshot = get_attempt_coverage_snapshot(conn, attempt_id=attempt_id, total_questions=24)
weights = coverage_soft_bias_weights(conn, attempt_id=attempt_id, total_questions=24)

# Shadow-only derived priority from soft weights, without touching legacy priority_order
shadow_priority = [
    pos for pos, _ in sorted(
        weights.items(),
        key=lambda kv: (-float(kv[1]), kv[0])
    )
]

summary = {
    "db": str(DB),
    "attempt_id": attempt_id,
    "legacy_snapshot": snapshot,
    "soft_bias_weights": weights,
    "shadow_priority_order": shadow_priority,
    "notes": [
        "Shadow-only report.",
        "Legacy attempt coverage contract preserved.",
        "Soft-bias priority is exploratory and not wired into selector/runtime in this layer."
    ],
}

path = OUT / "summary.json"
path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
print(path)
