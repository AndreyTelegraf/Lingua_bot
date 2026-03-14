import sqlite3
from pathlib import Path

DB = Path("/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")

BAD_DISTRACTORS = {
    "марк",
    "пётр",
    "петр",
}

def norm(s: str | None) -> str:
    return (s or "").strip().lower()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== SANITIZE WAVE 4 (RESIDUALS) ===")

rows = cur.execute("""
SELECT c.id, c.choice_text
FROM vocab_choices c
JOIN vocab_items i ON i.id = c.item_id
WHERE i.is_active = 1
  AND c.is_correct = 0
""").fetchall()

delete_ids = [r["id"] for r in rows if norm(r["choice_text"]) in BAD_DISTRACTORS]

if delete_ids:
    cur.executemany("DELETE FROM vocab_choices WHERE id = ?", [(x,) for x in delete_ids])

print("deleted_residual_bad_distractors:", len(delete_ids))

broken = cur.execute("""
SELECT
  i.id,
  i.lemma,
  COUNT(c.id) AS choice_count,
  SUM(CASE WHEN c.is_correct = 1 THEN 1 ELSE 0 END) AS correct_count
FROM vocab_items i
LEFT JOIN vocab_choices c ON c.item_id = i.id
WHERE i.is_active = 1
GROUP BY i.id, i.lemma
HAVING choice_count != 6 OR correct_count != 1
ORDER BY i.id
""").fetchall()

print("broken_before_rebuild:", len(broken))
for r in broken[:40]:
    print(f"broken\t{r['id']}\t{r['lemma']}\tchoices={r['choice_count']}\tcorrect={r['correct_count']}")

conn.commit()
conn.close()
