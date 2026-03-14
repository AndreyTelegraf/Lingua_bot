import random
import sqlite3
from pathlib import Path

DB = Path("/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")
random.seed(42)

BIN_ORDER = ["1K", "2K", "5K", "10K", "20K"]

BAD_EXACT = {
    "иван","даниил","максим","карл","фес","лима","европа",
    "январь","февраль","март","апрель","май","июнь","июль","август",
    "сентябрь","октябрь","ноябрь","декабрь",
    "блядь","говно","ети","діло",
    "португалия","испания","франция","италия","англия","греция","азия",
    "перу","россия","мексика","япония","китай","америка","африка",
    "филиппины","панама","уругвай","гвинея","алжир","венгрия","хорватия",
    "юнеско","гватемала",
    "андрей","александр","бруно","габриил","лука","михаил","рафаил",
    "фердинанд","иосиф","принц","господин","марк","пётр","петр",
}

BAD_SUBSTR = {
    "народная республика",
}

def norm(s: str | None) -> str:
    return (s or "").strip().lower()

def has_weird_chars(s: str) -> bool:
    return any(ch in s for ch in ("́", "`", "^", "~"))

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
    if len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]:
        return True
    if len(a) >= 4 and len(b) >= 4 and a[-4:] == b[-4:]:
        return True
    return False

def len_ok(correct: str, candidate: str) -> bool:
    lc = len(correct.strip())
    ld = abs(len(candidate.strip()) - lc)
    return ld <= max(2, round(lc * 0.35))

def bin_neighbors(bin_name: str | None):
    if bin_name not in BIN_ORDER:
        return BIN_ORDER[:]
    idx = BIN_ORDER.index(bin_name)
    order = [bin_name]
    for step in range(1, len(BIN_ORDER)):
        left = idx - step
        right = idx + step
        if left >= 0:
            order.append(BIN_ORDER[left])
        if right < len(BIN_ORDER):
            order.append(BIN_ORDER[right])
    return order

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== REBUILD HARDER CHOICES (SAME BIN / SAME POS / LENGTH AWARE) ===")

items = cur.execute("""
SELECT id, lemma, correct_answer, pos, bin_name
FROM vocab_items
WHERE is_active = 1
ORDER BY id
""").fetchall()

pool_rows = cur.execute("""
SELECT DISTINCT correct_answer, pos, bin_name
FROM vocab_items
WHERE is_active = 1
""").fetchall()

pool_by_pos_bin: dict[tuple[str, str], list[str]] = {}
pool_by_pos: dict[str, list[str]] = {}
global_pool: list[str] = []

for r in pool_rows:
    txt = r["correct_answer"]
    pos = norm(r["pos"])
    bin_name = (r["bin_name"] or "").strip()
    if is_bad_ru_gloss(txt):
        continue
    global_pool.append(txt)
    pool_by_pos.setdefault(pos, []).append(txt)
    pool_by_pos_bin.setdefault((pos, bin_name), []).append(txt)

global_pool = sorted(set(global_pool))
for k in list(pool_by_pos):
    pool_by_pos[k] = sorted(set(pool_by_pos[k]))
for k in list(pool_by_pos_bin):
    pool_by_pos_bin[k] = sorted(set(pool_by_pos_bin[k]))

print("active_items:", len(items))
print("clean_global_pool:", len(global_pool))
for pos in sorted(pool_by_pos):
    print(f"pool[{pos}]={len(pool_by_pos[pos])}")

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
    bin_name = (item["bin_name"] or "").strip()

    chosen = []
    seen = set()

    # 1) same pos + same bin + close length
    for b in bin_neighbors(bin_name):
        candidates = list(pool_by_pos_bin.get((pos, b), []))
        random.shuffle(candidates)
        for txt in candidates:
            if txt == correct or txt in seen:
                continue
            if is_bad_ru_gloss(txt):
                continue
            if morph_too_close(correct, txt):
                continue
            if not len_ok(correct, txt):
                continue
            chosen.append(txt)
            seen.add(txt)
            if len(chosen) == 5:
                break
        if len(chosen) == 5:
            break

    # 2) same pos + neighboring bins + looser length
    if len(chosen) < 5:
        for b in bin_neighbors(bin_name):
            candidates = list(pool_by_pos_bin.get((pos, b), []))
            random.shuffle(candidates)
            for txt in candidates:
                if txt == correct or txt in seen:
                    continue
                if is_bad_ru_gloss(txt):
                    continue
                if morph_too_close(correct, txt):
                    continue
                if abs(len(txt.strip()) - len(correct.strip())) > max(3, round(len(correct.strip()) * 0.5)):
                    continue
                chosen.append(txt)
                seen.add(txt)
                if len(chosen) == 5:
                    break
            if len(chosen) == 5:
                break

    # 3) same pos fallback
    if len(chosen) < 5:
        candidates = list(pool_by_pos.get(pos, []))
        random.shuffle(candidates)
        for txt in candidates:
            if txt == correct or txt in seen:
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
        hard_cases.append((item_id, item["lemma"], correct, pos, bin_name, len(chosen)))
        continue

    options = chosen + [correct]
    random.shuffle(options)

    for idx, txt in enumerate(options):
        choice_rows.append((item_id, txt, 1 if txt == correct else 0, idx))

cur.executemany("""
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index)
VALUES (?, ?, ?, ?)
""", choice_rows)

conn.commit()

print("inserted_choice_rows:", len(choice_rows))
print("hard_cases:", len(hard_cases))
for row in hard_cases[:50]:
    print("hard", row)

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
