import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DB = Path("/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")

if not DB.exists():
    raise SystemExit(f"db_not_found: {DB}")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== ACTIVE BANK SUMMARY ===")
row = cur.execute("""
SELECT
  COUNT(*) AS active_items,
  COUNT(DISTINCT LOWER(TRIM(lemma))) AS unique_lemmas
FROM vocab_items
WHERE is_active = 1
""").fetchone()
print(f"active_items: {row['active_items']}")
print(f"unique_lemmas: {row['unique_lemmas']}")
print()

print("=== CHOICE INTEGRITY ===")
row = cur.execute("""
SELECT
  SUM(CASE WHEN choice_count != 6 THEN 1 ELSE 0 END) AS bad_choice_count,
  SUM(CASE WHEN correct_count != 1 THEN 1 ELSE 0 END) AS bad_correct_count
FROM (
  SELECT
    i.id,
    COUNT(c.id) AS choice_count,
    SUM(CASE WHEN c.is_correct = 1 THEN 1 ELSE 0 END) AS correct_count
  FROM vocab_items i
  LEFT JOIN vocab_choices c ON c.item_id = i.id
  WHERE i.is_active = 1
  GROUP BY i.id
)
""").fetchone()
print(f"bad_choice_count: {row['bad_choice_count']}")
print(f"bad_correct_count: {row['bad_correct_count']}")
print()

print("=== BIN DISTRIBUTION ===")
rows = cur.execute("""
SELECT COALESCE(bin_name, '(null)') AS bin_name, COUNT(*) AS n
FROM vocab_items
WHERE is_active = 1
GROUP BY COALESCE(bin_name, '(null)')
ORDER BY
  CASE COALESCE(bin_name, '(null)')
    WHEN '1K' THEN 1
    WHEN '2K' THEN 2
    WHEN '5K' THEN 3
    WHEN '10K' THEN 4
    WHEN '20K' THEN 5
    WHEN 'B3' THEN 6
    WHEN 'B4' THEN 7
    WHEN 'B5' THEN 8
    WHEN 'B6' THEN 9
    ELSE 99
  END,
  bin_name
""").fetchall()
for r in rows:
    print(f"{r['bin_name']}: {r['n']}")
print()

print("=== CEFR DISTRIBUTION ===")
rows = cur.execute("""
SELECT COALESCE(level, '(null)') AS level, COUNT(*) AS n
FROM vocab_items
WHERE is_active = 1
GROUP BY COALESCE(level, '(null)')
ORDER BY
  CASE COALESCE(level, '(null)')
    WHEN 'A0' THEN 0
    WHEN 'A1' THEN 1
    WHEN 'A1+' THEN 2
    WHEN 'A2' THEN 3
    WHEN 'B1' THEN 4
    WHEN 'B2' THEN 5
    WHEN 'C1' THEN 6
    WHEN 'C1+' THEN 7
    ELSE 99
  END,
  level
""").fetchall()
for r in rows:
    print(f"{r['level']}: {r['n']}")
print()

print("=== POS DISTRIBUTION ===")
rows = cur.execute("""
SELECT COALESCE(pos, '(null)') AS pos, COUNT(*) AS n
FROM vocab_items
WHERE is_active = 1
GROUP BY COALESCE(pos, '(null)')
ORDER BY n DESC, pos
""").fetchall()
for r in rows:
    print(f"{r['pos']}: {r['n']}")
print()

print("=== TOPIC TAG DISTRIBUTION (TOP 25) ===")
rows = cur.execute("""
SELECT COALESCE(topic_tag, '(null)') AS topic_tag, COUNT(*) AS n
FROM vocab_items
WHERE is_active = 1
GROUP BY COALESCE(topic_tag, '(null)')
ORDER BY n DESC, topic_tag
LIMIT 25
""").fetchall()
for r in rows:
    print(f"{r['topic_tag']}: {r['n']}")
print()

print("=== DUPLICATE LEMMA+POS ===")
rows = cur.execute("""
SELECT LOWER(TRIM(lemma)) AS lemma_key,
       LOWER(TRIM(COALESCE(pos, ''))) AS pos_key,
       COUNT(*) AS n
FROM vocab_items
WHERE is_active = 1
GROUP BY lemma_key, pos_key
HAVING COUNT(*) > 1
ORDER BY n DESC, lemma_key, pos_key
LIMIT 50
""").fetchall()
if not rows:
    print("none")
else:
    for r in rows:
        print(f"{r['lemma_key']} [{r['pos_key']}] => {r['n']}")
print()

print("=== HOMOGRAPHS ACROSS POS ===")
rows = cur.execute("""
SELECT lemma_key, GROUP_CONCAT(pos_key, ',') AS pos_list, COUNT(*) AS pos_count
FROM (
  SELECT LOWER(TRIM(lemma)) AS lemma_key,
         LOWER(TRIM(COALESCE(pos, ''))) AS pos_key
  FROM vocab_items
  WHERE is_active = 1
  GROUP BY lemma_key, pos_key
)
GROUP BY lemma_key
HAVING COUNT(*) > 1
ORDER BY pos_count DESC, lemma_key
LIMIT 50
""").fetchall()
if not rows:
    print("none")
else:
    for r in rows:
        print(f"{r['lemma_key']} => {r['pos_list']}")
print()

print("=== DUPLICATE GLOSSES (TOP 50) ===")
rows = cur.execute("""
SELECT LOWER(TRIM(correct_answer)) AS gloss_key, COUNT(*) AS n
FROM vocab_items
WHERE is_active = 1
GROUP BY gloss_key
HAVING COUNT(*) > 1
ORDER BY n DESC, gloss_key
LIMIT 50
""").fetchall()
if not rows:
    print("none")
else:
    for r in rows:
        print(f"{r['gloss_key']} => {r['n']}")
print()

print("=== PROBABLE PROPER NOUNS / TOPONYMS (TOP 80) ===")
rows = cur.execute("""
SELECT id, lemma, correct_answer, pos, topic_tag, freq_rank, level, bin_name
FROM vocab_items
WHERE is_active = 1
  AND (
    LOWER(TRIM(lemma)) IN (
      'andré','bruno','felipe','gabriel','lucas','miguel','paris',
      'austrália','colômbia','grécia','inglaterra','peru','ásia',
      'portugal','espanha','frança','italia','italy','brasil',
      'rafael','alexandre','alessandro','felix','ares'
    )
    OR LOWER(TRIM(correct_answer)) IN (
      'андрей','бруно','фелипе','габриэл','лукас','мигель',
      'париж','австралия','колумбия','греция','англия','перу','азия',
      'португалия','испания','франция','италия','бразилия'
    )
    OR lemma GLOB '[A-ZА-Я]*'
  )
ORDER BY LOWER(TRIM(lemma))
LIMIT 80
""").fetchall()
if not rows:
    print("none")
else:
    for r in rows:
        print(f"{r['id']}\t{r['lemma']}\t{r['correct_answer']}\t{r['pos']}\t{r['bin_name']}")
print()

print("=== SAME-LEMMA / SAME-GLOSS LEAKS (TOP 80) ===")
rows = cur.execute("""
SELECT id, lemma, correct_answer, pos, bin_name
FROM vocab_items
WHERE is_active = 1
  AND LOWER(TRIM(lemma)) = LOWER(TRIM(correct_answer))
ORDER BY LOWER(TRIM(lemma))
LIMIT 80
""").fetchall()
if not rows:
    print("none")
else:
    for r in rows:
        print(f"{r['id']}\t{r['lemma']}\t{r['correct_answer']}\t{r['pos']}\t{r['bin_name']}")
print()

print("=== ITEMS WITH REPEATED DISTRACTOR SETS (TOP 50 SETS) ===")
rows = cur.execute("""
WITH choice_sets AS (
  SELECT
    c.item_id,
    GROUP_CONCAT(c.choice_text, ' || ') AS choice_set
  FROM (
    SELECT c.item_id, c.choice_text
    FROM vocab_choices c
    JOIN vocab_items i ON i.id = c.item_id
    WHERE i.is_active = 1
    ORDER BY c.item_id, c.choice_text
  ) c
  GROUP BY c.item_id
)
SELECT choice_set, COUNT(*) AS n
FROM choice_sets
GROUP BY choice_set
HAVING COUNT(*) > 1
ORDER BY n DESC
LIMIT 50
""").fetchall()
if not rows:
    print("none")
else:
    for r in rows:
        print(f"{r['n']}x :: {r['choice_set']}")
print()

print("=== SAMPLE ACTIVE ITEMS WITH CHOICES (FIRST 25) ===")
rows = cur.execute("""
SELECT
  i.id,
  i.lemma,
  i.correct_answer,
  i.pos,
  i.bin_name,
  c.position_index,
  c.choice_text,
  c.is_correct
FROM vocab_items i
JOIN vocab_choices c ON c.item_id = i.id
WHERE i.is_active = 1
ORDER BY i.id, c.position_index
LIMIT 25 * 6
""").fetchall()

current = None
for r in rows:
    if current != r["id"]:
        current = r["id"]
        print()
        print(f"[{r['id']}] {r['lemma']} -> {r['correct_answer']} | pos={r['pos']} | bin={r['bin_name']}")
    mark = "*" if r["is_correct"] else "-"
    print(f"  {mark} {r['position_index']}: {r['choice_text']}")

conn.close()
