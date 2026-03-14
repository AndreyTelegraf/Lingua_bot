import random
import sqlite3
from pathlib import Path

DB = Path("/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")
random.seed(42)

BAD_EXACT = {
    "иван","даниил","максим","карл","фес","лима","европа",
    "январь","февраль","март","апрель","май","июнь","июль","август",
    "сентябрь","октябрь","ноябрь","декабрь",
    "блядь","говно","ети","діло",
    "португалия","испания","франция","италия","англия","греция","азия",
    "перу","россия","мексика","япония","китай","америка","африка",
    "филиппины","панама","уругвай","гвинея",
    "андрей","александр","бруно","габриил","лука","михаил","рафаил",
    "фердинанд","иосиф","принц","господин",
}

BAD_SUBSTR = {
    "народная республика",
}

def norm(s: str | None) -> str:
    return (s or "").strip().lower()

def has_weird_chars(s: str) -> bool:
    bad = set("́`^~")
    return any(ch in bad for ch in s)

def is_bad_ru_gloss(text: str) -> bool:
    t = norm(text)
    if not t:
        return True
    if len(t) <= 2:
        return True
    if t in BAD_EXACT:
        return True
    if any(x in t for x in BAD_SUBSTR):
        return True
    if has_weird_chars(t):
        return True
    return False

def morph_too_close(a: str, b: str) -> bool:
    a = norm(a)
    b = norm(b)
    if not a or not b or a == b:
        return True
    if a.startswith(b) or b.startswith(a):
        return True
    if a.endswith(b) or b.endswith(a):
        return True
    if abs(len(a) - len(b)) <= 2 and (a[:4] == b[:4] or a[-4:] == b[-4:]):
        return True
    return False

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== REBUILD CHOICES FROM CLEAN RU POOL ===")

# active items
items = cur.execute("""
SELECT id, lemma, correct_answer, pos, bin_name
FROM vocab_items
WHERE is_active = 1
ORDER BY id
""").fetchall()

# cleaned pool from active correct answers
pool_rows = cur.execute("""
SELECT DISTINCT correct_answer, pos
FROM vocab_items
WHERE is_active = 1
""").fetchall()

pool_by_pos: dict[str, list[str]] = {}
global_pool: list[str] = []

for r in pool_rows:
    txt = r["correct_answer"]
    pos = norm(r["pos"])
    if is_bad_ru_gloss(txt):
        continue
    global_pool.append(txt)
    pool_by_pos.setdefault(pos, []).append(txt)

global_pool = sorted(set(global_pool))
for k in list(pool_by_pos.keys()):
    pool_by_pos[k] = sorted(set(pool_by_pos[k]))

print("active_items:", len(items))
print("clean_global_pool:", len(global_pool))
for k in sorted(pool_by_pos):
    print(f"pool[{k}]={len(pool_by_pos[k])}")

# wipe active choices only
cur.execute("""
DELETE FROM vocab_choices
WHERE item_id IN (
  SELECT id FROM vocab_items WHERE is_active = 1
)
""")

choice_rows = []
hard_cases = []

for item in items:
    item_id = item["id"]
    correct = item["correct_answer"]
    pos = norm(item["pos"])

    same_pos_pool = pool_by_pos.get(pos, [])
    candidates = []

    for txt in same_pos_pool:
        if txt == correct:
            continue
        if is_bad_ru_gloss(txt):
            continue
        if morph_too_close(correct, txt):
            continue
        candidates.append(txt)

    random.shuffle(candidates)
    chosen = []
    seen = set()

    for txt in candidates:
        if txt in seen:
            continue
        chosen.append(txt)
        seen.add(txt)
        if len(chosen) == 5:
            break

    if len(chosen) < 5:
        fallback = global_pool[:]
        random.shuffle(fallback)
        for txt in fallback:
            if txt == correct:
                continue
            if txt in seen:
                continue
            if is_bad_ru_gloss(txt):
                continue
            if morph_too_close(correct, txt):
                continue
            chosen.append(txt)
            seen.add(txt)
            if len(chosen) == 5:
                break

    if len(chosen) < 5:
        hard_cases.append((item_id, item["lemma"], correct, pos, len(chosen)))
        continue

    options = chosen + [correct]
    random.shuffle(options)

    for idx, txt in enumerate(options):
        choice_rows.append(
            (item_id, txt, 1 if txt == correct else 0, idx)
        )

cur.executemany("""
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index)
VALUES (?, ?, ?, ?)
""", choice_rows)

conn.commit()

print("inserted_choice_rows:", len(choice_rows))
print("hard_cases:", len(hard_cases))
for row in hard_cases[:50]:
    print("hard", row)

# targeted fix for known last leak if still present
rows = cur.execute("""
SELECT
  i.id AS item_id,
  i.correct_answer AS correct_answer,
  c.id AS choice_id,
  c.choice_text AS choice_text
FROM vocab_items i
JOIN vocab_choices c ON c.item_id = i.id
WHERE i.is_active = 1 AND c.is_correct = 0
ORDER BY i.id, c.position_index
""").fetchall()

delete_ids = []
for r in rows:
    if morph_too_close(r["correct_answer"], r["choice_text"]):
        delete_ids.append(r["choice_id"])

if delete_ids:
    cur.executemany("DELETE FROM vocab_choices WHERE id = ?", [(x,) for x in sorted(set(delete_ids))])
    conn.commit()

print("post_insert_deleted_morph_leaks:", len(set(delete_ids)))

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

print("broken_after_rebuild:", len(broken))
for r in broken[:50]:
    print(f"broken\t{r['id']}\t{r['lemma']}\tchoices={r['choice_count']}\tcorrect={r['correct_count']}")

conn.close()
