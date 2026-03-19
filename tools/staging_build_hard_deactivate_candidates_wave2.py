from __future__ import annotations
import csv
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_build_hard_deactivate_candidates_wave2"
OUT_DIR.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

item_cols = [r["name"] for r in cur.execute("PRAGMA table_info(vocab_items)")]
choice_cols = [r["name"] for r in cur.execute("PRAGMA table_info(vocab_choices)")]

active_col = "is_active" if "is_active" in item_cols else "active"
pk_col = "id"

rows = cur.execute(f"""
    SELECT
        vi.{pk_col} AS item_id,
        vi.lemma,
        vi.question_text,
        vi.correct_answer,
        vi.pos,
        vi.topic_tag,
        vi.bin_name,
        vi.freq_rank,
        vi.{active_col} AS active_value
    FROM vocab_items vi
    WHERE vi.{active_col} = 1
""").fetchall()

choices_by_item: dict[int, list[str]] = {}
if {"item_id", "choice_text"} <= set(choice_cols):
    for r in cur.execute("""
        SELECT item_id, choice_text
        FROM vocab_choices
        ORDER BY item_id, position_index, id
    """):
        choices_by_item.setdefault(int(r["item_id"]), []).append(r["choice_text"])

functionish_lemmas = {
    "já", "só", "bem", "mal", "ainda", "também", "então", "assim", "aqui", "ali",
    "agora", "sempre", "nunca", "depois", "antes", "hoje", "ontem", "amanhã",
}

bad_ru_glosses = {
    "курка",
    "бывать",
}

def looks_like_proper_name(row: sqlite3.Row) -> bool:
    lemma = (row["lemma"] or "").strip().lower()
    ans = (row["correct_answer"] or "").strip().lower()
    topic = (row["topic_tag"] or "").strip().lower()
    if topic.startswith("build:pilot_ptpt_001_pilot_safe") and lemma in {
        "fernando", "joão", "maria", "josé", "antonio", "antónio",
        "manuel", "pedro", "ana", "carlos", "paulo", "luis", "luís",
    }:
        return True
    if lemma == ans:
        return True
    return False

def is_short_answer(row: sqlite3.Row) -> bool:
    ans = (row["correct_answer"] or "").strip()
    return len(ans) <= 5

def weird_ru_gloss(row: sqlite3.Row) -> bool:
    ans = (row["correct_answer"] or "").strip().lower()
    return ans in bad_ru_glosses

def functionish_surface(row: sqlite3.Row) -> bool:
    lemma = (row["lemma"] or "").strip().lower()
    pos = (row["pos"] or "").strip().lower()
    return pos == "adverb" and lemma in functionish_lemmas

def suspicious_choice_pack(row: sqlite3.Row) -> bool:
    item_id = int(row["item_id"])
    choices = choices_by_item.get(item_id, [])
    if len(choices) != 6:
        return False
    short_choices = sum(1 for c in choices if len((c or "").strip()) <= 5)
    return short_choices >= 5 and is_short_answer(row)

candidates: list[dict] = []

for r in rows:
    reasons: list[str] = []
    if looks_like_proper_name(r):
        reasons.append("proper_name_like")
    if weird_ru_gloss(r):
        reasons.append("awkward_ru_gloss")
    if functionish_surface(r):
        reasons.append("functionish_surface")
    if suspicious_choice_pack(r):
        reasons.append("short_choice_pack")
    if not reasons:
        continue

    item_id = int(r["item_id"])
    candidates.append({
        "item_id": item_id,
        "lemma": r["lemma"],
        "correct_answer": r["correct_answer"],
        "pos": r["pos"],
        "topic_tag": r["topic_tag"],
        "bin_name": r["bin_name"],
        "freq_rank": r["freq_rank"],
        "reasons": "|".join(reasons),
        "choices_preview": " || ".join(choices_by_item.get(item_id, [])[:6]),
    })

candidates.sort(key=lambda x: (x["bin_name"] or "", x["freq_rank"] or 999999, x["item_id"]))

csv_path = OUT_DIR / "hard_deactivate_candidates_wave2.csv"
with csv_path.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(
        f,
        fieldnames=[
            "item_id", "lemma", "correct_answer", "pos", "topic_tag",
            "bin_name", "freq_rank", "reasons", "choices_preview",
        ],
    )
    w.writeheader()
    w.writerows(candidates)

summary = {
    "db": str(DB),
    "active_total": cur.execute(f"SELECT COUNT(*) AS c FROM vocab_items WHERE {active_col}=1").fetchone()["c"],
    "candidate_count": len(candidates),
    "reason_counts": dict(Counter(
        reason
        for row in candidates
        for reason in row["reasons"].split("|")
    )),
    "csv": str(csv_path),
    "utc_timestamp": datetime.now(timezone.utc).isoformat(),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(summary, ensure_ascii=False, indent=2))
conn.close()
