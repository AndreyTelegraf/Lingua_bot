from pathlib import Path
import sys
import sqlite3, json, time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DB = "data/lingua_staging.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

pos_counts = dict(conn.execute(
    "SELECT pos, COUNT(*) FROM vocab_items WHERE is_active=1 GROUP BY pos"
).fetchall())

out = {
    "active_pos_distribution": pos_counts
}

p = Path(f"artifacts/vocab_forensics_{int(time.time())}")
p.mkdir(parents=True, exist_ok=True)

(p / "summary.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
