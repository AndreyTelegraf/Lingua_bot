import json
import sqlite3
from pathlib import Path

DB = Path("/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")
AUDIT = Path("/tmp/full_vocab_audit.json")

if not DB.exists():
    raise SystemExit(f"db_not_found: {DB}")
if not AUDIT.exists():
    raise SystemExit(f"audit_not_found: {AUDIT}")

report = json.loads(AUDIT.read_text(encoding="utf-8"))

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== APPLY FULL AUDIT CLEANUP ===")

# 1) deactivate suspicious / banned items entirely
bad_item_ids = sorted({
    int(r["id"])
    for r in report.get("banned_or_suspicious_items", [])
})

if bad_item_ids:
    cur.executemany(
        "UPDATE vocab_items SET is_active = 0 WHERE id = ?",
        [(x,) for x in bad_item_ids]
    )

print("deactivated_items:", len(bad_item_ids))

# 2) delete choice rows for inactive items
cur.execute("""
DELETE FROM vocab_choices
WHERE item_id IN (
  SELECT id FROM vocab_items WHERE is_active = 0
)
""")
print("deleted_choices_for_inactive:", cur.rowcount)

# 3) additionally deactivate items whose own correct_answer is flagged as bad choice text
bad_choice_item_ids = sorted({
    int(r["item_id"])
    for r in report.get("bad_choice_rows", [])
})

if bad_choice_item_ids:
    cur.executemany(
        "UPDATE vocab_items SET is_active = 0 WHERE id = ?",
        [(x,) for x in bad_choice_item_ids]
    )

print("deactivated_bad_choice_items:", len(bad_choice_item_ids))

# 4) remove any choices for newly deactivated items
cur.execute("""
DELETE FROM vocab_choices
WHERE item_id IN (
  SELECT id FROM vocab_items WHERE is_active = 0
)
""")
print("deleted_choices_after_bad_choice_deactivate:", cur.rowcount)

# 5) final counts before rebuild
active_items = cur.execute("""
SELECT COUNT(*) AS n
FROM vocab_items
WHERE is_active = 1
""").fetchone()["n"]

active_choices = cur.execute("""
SELECT COUNT(*) AS n
FROM vocab_choices c
JOIN vocab_items i ON i.id = c.item_id
WHERE i.is_active = 1
""").fetchone()["n"]

print("active_items_before_rebuild:", active_items)
print("active_choices_before_rebuild:", active_choices)

conn.commit()
conn.close()
