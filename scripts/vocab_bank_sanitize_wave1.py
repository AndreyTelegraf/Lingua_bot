import sqlite3
from pathlib import Path

DB = Path("/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")

BAN_LEMMAS = {
    # names
    "alessandro","alexandre","andré","ares","bruno","felipe","gabriel",
    "lucas","miguel","rafael",
    # places / countries / regions / cities
    "austrália","colômbia","espanha","frança","grécia","inglaterra",
    "itália","paris","peru","portugal","ásia",
    # noisy likely proper nouns seen in samples / prior runs
    "daniil","eduard","fés",
}

BAN_GLOSSES = {
    "александр","андрей","бруно","филип","габриил","лука","михаил","рафаил",
    "австралия","колумбия","испания","франция","греция","англия","италия",
    "париж","перу","португалия","азия",
    # obvious bad / noisy outputs
    "говно",
}

def normalize(s: str | None) -> str:
    return (s or "").strip().lower()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== SANITIZE WAVE 1 ===")

# 1) deactivate obvious proper nouns / toponyms / banned glosses
rows = cur.execute("""
SELECT id, lemma, correct_answer, pos, topic_tag, bin_name
FROM vocab_items
WHERE is_active = 1
""").fetchall()

to_deactivate = []
for r in rows:
    lemma = normalize(r["lemma"])
    gloss = normalize(r["correct_answer"])
    if lemma in BAN_LEMMAS or gloss in BAN_GLOSSES:
        to_deactivate.append(r["id"])

if to_deactivate:
    cur.executemany(
        "UPDATE vocab_items SET is_active = 0 WHERE id = ?",
        [(x,) for x in to_deactivate]
    )

print("deactivated_items:", len(to_deactivate))

# 2) delete choice rows for inactive items
cur.execute("""
DELETE FROM vocab_choices
WHERE item_id IN (
  SELECT id FROM vocab_items WHERE is_active = 0
)
""")
print("deleted_choices_for_inactive:", cur.rowcount)

# 3) remove single-char / empty / obviously bad choice rows on active items
bad_choice_rows = cur.execute("""
SELECT c.id
FROM vocab_choices c
JOIN vocab_items i ON i.id = c.item_id
WHERE i.is_active = 1
  AND (
    LENGTH(TRIM(c.choice_text)) <= 1
    OR LOWER(TRIM(c.choice_text)) IN ('m', '—', '-', 'null')
    OR LOWER(TRIM(c.choice_text)) IN ('говно')
  )
""").fetchall()

bad_choice_ids = [r["id"] for r in bad_choice_rows]
if bad_choice_ids:
    cur.executemany("DELETE FROM vocab_choices WHERE id = ?", [(x,) for x in bad_choice_ids])
print("deleted_bad_choice_rows:", len(bad_choice_ids))

# 4) find active items now broken by choice count / correct count
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

print("broken_items_after_cleanup:", len(broken))
for r in broken[:50]:
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
