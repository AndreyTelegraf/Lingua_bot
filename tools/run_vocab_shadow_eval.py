from pathlib import Path
import sys
import sqlite3, json, time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.vocab_runtime.attempt_coverage import (
    coverage_priority_order,
    coverage_soft_bias_weights
)

DB = "data/lingua_staging.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

attempts = [r["attempt_id"] for r in conn.execute(
    "SELECT DISTINCT attempt_id FROM vocab_answers ORDER BY attempt_id DESC LIMIT 200"
)]

diff = 0
total = 0

for aid in attempts:
    legacy = coverage_priority_order(conn, attempt_id=aid, total_questions=24)
    weights = coverage_soft_bias_weights(conn, attempt_id=aid, total_questions=24)

    shadow = sorted(weights.keys(), key=lambda k: weights[k], reverse=True)

    if legacy != shadow:
        diff += 1
    total += 1

out = {
    "attempts": total,
    "changed_priority": diff,
    "change_rate": round(diff / total, 3) if total else 0
}

p = Path(f"artifacts/vocab_shadow_eval_{int(time.time())}")
p.mkdir(parents=True, exist_ok=True)

(p / "summary.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
