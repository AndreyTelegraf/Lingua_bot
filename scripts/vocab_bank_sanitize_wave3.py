import sqlite3
from pathlib import Path

DB = Path("/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")

BAD_CHOICE_TEXT = {
    # countries / places / regions
    "россия","мексика","китай","китайская народная республика","япония",
    "америка","африка","индия","панама","уругвай","гвинея","китайская республика",
    "португалия","испания","франция","италия","англия","греция","азия","перу",
    "филиппины",
    # personal names / biblical / person-like
    "иван","иосиф","карл","фердинанд","александр","андрей","бруно","лука",
    "михаил","рафаил","габриил","филип","принц","господин",
    # noisy geo/name leftovers
    "лима","фес",
    # profanity / junk
    "блядь","говно",
}

# glosses with combining accent / weird orthography
def has_weird_markers(text: str) -> bool:
    return any(ch in text for ch in ("́", "`", "̂", "̃"))

# homographs across POS where noun/adjective duplication is more harmful than useful
HOMOGRAPH_DEACTIVATE = {
    ("acre", "adjective"),
    ("alemão", "noun"),
    ("aliado", "noun"),
    ("bruto", "noun"),
    ("cardeal", "noun"),
    ("cinza", "noun"),
    ("comercial", "noun"),
    ("comunista", "noun"),
    ("concreto", "noun"),
    ("condenado", "noun"),
    ("funeral", "noun"),
    ("ideal", "noun"),
    ("idiota", "noun"),
    ("italiano", "noun"),
    ("mexicano", "noun"),
    ("militar", "noun"),
    ("moral", "noun"),
    ("mágico", "noun"),
    ("negativo", "noun"),
    ("negro", "noun"),
    ("noturno", "noun"),
    ("oceano", "adjective"),
    ("pessoal", "noun"),
    ("plural", "noun"),
    ("político", "noun"),
    ("português", "noun"),
    ("positivo", "noun"),
    ("químico", "noun"),
    ("rosa", "adjective"),
    ("russo", "noun"),
    ("singular", "noun"),
    ("sérvio", "noun"),
    ("técnico", "noun"),
    ("variável", "noun"),
    ("velho", "noun"),
}

def norm(s: str | None) -> str:
    return (s or "").strip().lower()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== SANITIZE WAVE 3 ===")

# 1) deactivate selected homograph items
rows = cur.execute("""
SELECT id, lemma, pos
FROM vocab_items
WHERE is_active = 1
""").fetchall()

deactivate_ids = []
for r in rows:
    key = (norm(r["lemma"]), norm(r["pos"]))
    if key in HOMOGRAPH_DEACTIVATE:
        deactivate_ids.append(r["id"])

if deactivate_ids:
    cur.executemany(
        "UPDATE vocab_items SET is_active = 0 WHERE id = ?",
        [(x,) for x in deactivate_ids]
    )

print("deactivated_homograph_items:", len(deactivate_ids))

# 2) delete choices for inactive items
cur.execute("""
DELETE FROM vocab_choices
WHERE item_id IN (
  SELECT id FROM vocab_items WHERE is_active = 0
)
""")
print("deleted_choices_for_inactive:", cur.rowcount)

# 3) remove noisy distractors from active items
rows = cur.execute("""
SELECT c.id, c.choice_text
FROM vocab_choices c
JOIN vocab_items i ON i.id = c.item_id
WHERE i.is_active = 1
  AND c.is_correct = 0
""").fetchall()

delete_choice_ids = []
for r in rows:
    txt = norm(r["choice_text"])
    if txt in BAD_CHOICE_TEXT:
        delete_choice_ids.append(r["id"])
        continue
    if has_weird_markers(txt):
        delete_choice_ids.append(r["id"])
        continue
    if len(txt) <= 2:
        delete_choice_ids.append(r["id"])
        continue

if delete_choice_ids:
    cur.executemany(
        "DELETE FROM vocab_choices WHERE id = ?",
        [(x,) for x in sorted(set(delete_choice_ids))]
    )

print("deleted_bad_distractors:", len(set(delete_choice_ids)))

# 4) broken items report before rebuild
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
for r in broken[:80]:
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
