import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DB = Path("/home/andrey/Projects/lingua_bot_v2/data/lingua_staging.db")

BANNED_LEMMAS = {
    "escócia","roraima","ares","paradigma",
    "andré","bruno","felipe","gabriel","lucas","miguel","rafael",
    "austrália","colômbia","espanha","frança","grécia","inglaterra",
    "itália","paris","peru","portugal","ásia",
}
BANNED_GLOSSES = {
    "шотландия","рорайма","арес","парадигма",
    "андрей","бруно","филип","габриил","лука","михаил","рафаил",
    "австралия","колумбия","испания","франция","греция","англия",
    "италия","париж","перу","португалия","азия",
    "говно","блядь",
}
BAD_CHOICE_EXACT = {
    "иван","даниил","максим","карл","марк","пётр","петр","фес","лима",
    "январь","февраль","март","апрель","май","июнь","июль","август",
    "сентябрь","октябрь","ноябрь","декабрь",
    "россия","мексика","япония","китай","америка","африка",
    "алжир","венгрия","хорватия","гватемала","юнеско",
    "ети","діло","говно","блядь",
}
BAD_SUBSTR = {
    "народная республика",
}

def norm(s):
    return (s or "").strip().lower()

def has_weird(s: str) -> bool:
    return any(ch in s for ch in ("́", "`", "^", "~"))

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

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

report = {}

active_items = cur.execute("""
SELECT id, lemma, correct_answer, pos, bin_name, level, topic_tag
FROM vocab_items
WHERE is_active = 1
ORDER BY id
""").fetchall()

choices = cur.execute("""
SELECT c.item_id, c.choice_text, c.is_correct, c.position_index
FROM vocab_choices c
JOIN vocab_items i ON i.id = c.item_id
WHERE i.is_active = 1
ORDER BY c.item_id, c.position_index
""").fetchall()

report["active_items"] = len(active_items)
report["active_choice_rows"] = len(choices)

bad_items = []
for r in active_items:
    lemma = norm(r["lemma"])
    gloss = norm(r["correct_answer"])
    if lemma in BANNED_LEMMAS or gloss in BANNED_GLOSSES or has_weird(gloss):
        bad_items.append({
            "id": r["id"],
            "lemma": r["lemma"],
            "correct_answer": r["correct_answer"],
            "pos": r["pos"],
            "bin_name": r["bin_name"],
        })

report["banned_or_suspicious_items"] = bad_items

by_item = defaultdict(list)
for r in choices:
    by_item[r["item_id"]].append(r)

bad_choice_rows = []
morph_leaks = []
repeated_sets_counter = Counter()

for item in active_items:
    item_id = item["id"]
    correct = item["correct_answer"]
    item_choices = by_item[item_id]

    choice_texts = [c["choice_text"] for c in item_choices]
    repeated_sets_counter[tuple(sorted(choice_texts))] += 1

    for c in item_choices:
        txt = norm(c["choice_text"])
        if txt in BAD_CHOICE_EXACT or any(x in txt for x in BAD_SUBSTR) or has_weird(txt):
            bad_choice_rows.append({
                "item_id": item_id,
                "lemma": item["lemma"],
                "correct_answer": item["correct_answer"],
                "choice_text": c["choice_text"],
            })
        if not c["is_correct"] and morph_too_close(correct, c["choice_text"]):
            morph_leaks.append({
                "item_id": item_id,
                "lemma": item["lemma"],
                "correct_answer": correct,
                "choice_text": c["choice_text"],
            })

report["bad_choice_rows"] = bad_choice_rows
report["morph_leaks"] = morph_leaks

dup_lemma_pos = cur.execute("""
SELECT LOWER(TRIM(lemma)) AS lemma_key,
       LOWER(TRIM(COALESCE(pos,''))) AS pos_key,
       COUNT(*) AS n
FROM vocab_items
WHERE is_active = 1
GROUP BY lemma_key, pos_key
HAVING COUNT(*) > 1
ORDER BY n DESC, lemma_key, pos_key
""").fetchall()
report["duplicate_lemma_pos"] = [dict(r) for r in dup_lemma_pos]

dup_gloss = cur.execute("""
SELECT LOWER(TRIM(correct_answer)) AS gloss_key, COUNT(*) AS n
FROM vocab_items
WHERE is_active = 1
GROUP BY gloss_key
HAVING COUNT(*) > 1
ORDER BY n DESC, gloss_key
LIMIT 100
""").fetchall()
report["duplicate_glosses"] = [dict(r) for r in dup_gloss]

homographs = cur.execute("""
SELECT lemma_key, GROUP_CONCAT(pos_key, ',') AS pos_list, COUNT(*) AS pos_count
FROM (
  SELECT LOWER(TRIM(lemma)) AS lemma_key,
         LOWER(TRIM(COALESCE(pos,''))) AS pos_key
  FROM vocab_items
  WHERE is_active = 1
  GROUP BY lemma_key, pos_key
)
GROUP BY lemma_key
HAVING COUNT(*) > 1
ORDER BY pos_count DESC, lemma_key
""").fetchall()
report["homographs_across_pos"] = [dict(r) for r in homographs]

report["repeated_choice_sets"] = [
    {"count": n, "choice_set": list(k)}
    for k, n in repeated_sets_counter.items()
    if n > 1
]

report["pos_distribution"] = [
    dict(r) for r in cur.execute("""
        SELECT pos, COUNT(*) AS n
        FROM vocab_items
        WHERE is_active = 1
        GROUP BY pos
        ORDER BY n DESC, pos
    """).fetchall()
]

report["bin_distribution"] = [
    dict(r) for r in cur.execute("""
        SELECT bin_name, COUNT(*) AS n
        FROM vocab_items
        WHERE is_active = 1
        GROUP BY bin_name
        ORDER BY n DESC, bin_name
    """).fetchall()
]

print(json.dumps(report, ensure_ascii=False, indent=2))
conn.close()
