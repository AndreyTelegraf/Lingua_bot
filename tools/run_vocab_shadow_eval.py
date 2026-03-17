from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.vocab_runtime.attempt_coverage import (
    coverage_priority_order,
    coverage_priority_order_soft_bias,
)

DB = ROOT / "data/lingua_staging.db"
OUT = ROOT / "artifacts" / f"vocab_shadow_eval_{__import__('time').time_ns() // 1_000_000_000}"
OUT.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

attempt_ids = [
    r["attempt_id"]
    for r in conn.execute(
        "SELECT DISTINCT attempt_id FROM vocab_answers ORDER BY attempt_id"
    ).fetchall()
]

changed = 0
rows = []
for aid in attempt_ids:
    legacy = coverage_priority_order(conn, attempt_id=aid, total_questions=24)
    soft = coverage_priority_order_soft_bias(conn, attempt_id=aid, total_questions=24)
    is_changed = legacy != soft
    if is_changed:
        changed += 1
    rows.append(
        {
            "attempt_id": aid,
            "legacy_priority": legacy,
            "soft_priority": soft,
            "changed": is_changed,
        }
    )

summary = {
    "attempts": len(attempt_ids),
    "changed_priority": changed,
    "change_rate": round(changed / len(attempt_ids), 6) if attempt_ids else 0.0,
}

(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "details.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
