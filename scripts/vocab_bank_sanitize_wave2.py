import sqlite3
from pathlib import Path

DB = Path("/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")

BAD_CHOICE_TEXT = {
    "блядь",
    "иван",
    "карл",
    "лима",
    "фердинанд",
    "филиппины",
    "америка",
    "британец",
    "фес",
    "арес",
    "александр",
    "андрей",
    "бруно",
    "габриил",
    "лука",
    "михаил",
    "рафаил",
    "австралия",
    "колумбия",
    "испания",
    "франция",
    "греция",
    "англия",
    "италия",
    "париж",
    "португалия",
    "азия",
    "перу",
}

BAD_ITEM_GLOSSES = {
    "блядь",
}

def norm(s: str | None) -> str:
    return (s or "").strip().lower()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== SANITIZE WAVE 2 ===")

# 1) deactivate active items with explicitly banned Russian glosses
rows = cur.execute("""
SELECT id, lemma, correct_answer
FROM vocab_items
WHERE is_active = 1
""").fetchall()

deactivate_ids = []
for r in rows:
    if norm(r["correct_answer"]) in BAD_ITEM_GLOSSES:
        deactivate_ids.append(r["id"])

if deactivate_ids:
    cur.executemany(
        "UPDATE vocab_items SET is_active = 0 WHERE id = ?",
        [(x,) for x in deactivate_ids]
    )

print("deactivated_items:", len(deactivate_ids))

# 2) delete choices for inactive items
cur.execute("""
DELETE FROM vocab_choices
WHERE item_id IN (
  SELECT id FROM vocab_items WHERE is_active = 0
)
""")
print("deleted_choices_for_inactive:", cur.rowcount)

# 3) delete banned / noisy distractors from active items
choice_rows = cur.execute("""
SELECT c.id, c.choice_text, c.is_correct, c.item_id
FROM vocab_choices c
JOIN vocab_items i ON i.id = c.item_id
WHERE i.is_active = 1
""").fetchall()

delete_choice_ids = []
for r in choice_rows:
    txt = norm(r["choice_text"])
    if txt in BAD_CHOICE_TEXT:
        delete_choice_ids.append(r["id"])
        continue
    if len(txt) <= 1:
        delete_choice_ids.append(r["id"])
        continue

if delete_choice_ids:
    cur.executemany(
        "DELETE FROM vocab_choices WHERE id = ?",
        [(x,) for x in delete_choice_ids]
    )

print("deleted_bad_choice_rows:", len(delete_choice_ids))

# 4) remove simple morph leaks:
# if distractor startswith/endswith correct or correct startswith distractor
rows = cur.execute("""
SELECT
  i.id AS item_id,
  i.correct_answer AS correct_answer,
  c.id AS choice_id,
  c.choice_text AS choice_text
FROM vocab_items i
JOIN vocab_choices c ON c.item_id = i.id
WHERE i.is_active = 1
  AND c.is_correct = 0
ORDER BY i.id, c.position_index
""").fetchall()

morph_delete_ids = []
for r in rows:
    correct = norm(r["correct_answer"])
    choice = norm(r["choice_text"])
    if not correct or not choice:
        continue
    if correct.startswith(choice) or choice.startswith(correct):
        morph_delete_ids.append(r["choice_id"])
        continue
    if correct.endswith(choice) or choice.endswith(correct):
        morph_delete_ids.append(r["choice_id"])
        continue

if morph_delete_ids:
    cur.executemany(
        "DELETE FROM vocab_choices WHERE id = ?",
        [(x,) for x in sorted(set(morph_delete_ids))]
    )

print("deleted_morph_leak_choices:", len(set(morph_delete_ids)))

# 5) report broken items before rebuild
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

print("broken_items_before_rebuild:", len(broken))
for r in broken[:60]:
    print(f"broken\t{r['id']}\t{r['lemma']}\tchoices={r['choice_count']}\tcorrect={r['correct_count']}")

conn.commit()

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

print()
print("active_items:", active_items)
print("active_choices:", active_choices)

conn.close()
