from __future__ import annotations
import csv
import json
import sqlite3
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
IN_CSV = ROOT / "data/master_source_v1/processed/staging_mixed_legacy_length_workbench_wave1/mixed_legacy_manual_review.csv"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_legacy_manual_review_batch_pack_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not DB.exists():
    raise SystemExit(f"DB not found: {DB}")
if not IN_CSV.exists():
    raise SystemExit(f"Missing input CSV: {IN_CSV}")

FUNCTIONISH = {
    "agora", "ainda", "já", "ja", "só", "so", "nem", "também", "tambem",
    "senão", "senao", "todo", "toda", "todos", "todas", "boa", "bom",
    "última", "ultima", "último", "ultimo", "único", "unico", "única", "unica",
    "bastante"
}
SHORT_BAD = {"око"}
BINS_HOT = {"1K", "2K"}

def norm(x) -> str:
    return "" if x is None else str(x).strip()

def is_short(text: str) -> bool:
    return len(text) <= 4

with IN_CSV.open("r", encoding="utf-8-sig", newline="") as f:
    src_rows = list(csv.DictReader(f))

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

table_info = [dict(r) for r in cur.execute("PRAGMA table_info(vocab_items)").fetchall()]
col_names = [r["name"] for r in table_info]
pk_col = next((r["name"] for r in table_info if int(r["pk"]) == 1), None) or ("id" if "id" in col_names else "item_id")
active_col = "is_active" if "is_active" in col_names else "active"

choice_info = [dict(r) for r in cur.execute("PRAGMA table_info(vocab_choices)").fetchall()]
choice_cols = [r["name"] for r in choice_info]
choice_item_col = "item_id" if "item_id" in choice_cols else None
choice_text_col = "choice_text" if "choice_text" in choice_cols else None
choice_pos_col = "position_index" if "position_index" in choice_cols else None
if not choice_item_col or not choice_text_col:
    raise SystemExit("Could not detect vocab_choices shape")

def load_choices(item_id: int) -> list[str]:
    sql = f"SELECT {choice_text_col} AS choice_text FROM vocab_choices WHERE {choice_item_col} = ?"
    if choice_pos_col:
        sql += f" ORDER BY {choice_pos_col}"
    rows = [norm(r["choice_text"]) for r in cur.execute(sql, (item_id,)).fetchall()]
    out = []
    seen = set()
    for x in rows:
        if x and x not in seen:
            out.append(x)
            seen.add(x)
    return out

pack = []
for src in src_rows:
    item_pk = int(src["item_pk"])
    row = cur.execute(
        f"SELECT {pk_col} AS item_pk, lemma, correct_answer, pos, topic_tag, bin_name, freq_rank, {active_col} AS active_value "
        f"FROM vocab_items WHERE {pk_col} = ?",
        (item_pk,),
    ).fetchone()
    if row is None:
        continue
    row = dict(row)

    lemma = norm(row["lemma"])
    correct = norm(row["correct_answer"])
    pos = norm(row["pos"])
    topic_tag = norm(row["topic_tag"])
    bin_name = norm(row["bin_name"])
    source_family = norm(src["source_family"])
    freq_rank = row["freq_rank"]
    choices = load_choices(item_pk)

    priority_score = 0
    priority_reasons = []

    if source_family == "pilot_safe":
        priority_score += 50
        priority_reasons.append("pilot_safe")
    elif source_family == "enriched_qc":
        priority_score += 35
        priority_reasons.append("enriched_qc")
    elif source_family == "kaikki":
        priority_score += 20
        priority_reasons.append("kaikki")

    if bin_name in BINS_HOT:
        priority_score += 40
        priority_reasons.append(f"hot_bin:{bin_name}")
    elif bin_name == "5K":
        priority_score += 20
        priority_reasons.append("bin:5K")

    if is_short(correct):
        priority_score += 20
        priority_reasons.append("short_correct")
    if correct in SHORT_BAD:
        priority_score += 15
        priority_reasons.append("odd_short_translation")
    if lemma.lower() in FUNCTIONISH:
        priority_score += 25
        priority_reasons.append("functionish_lemma")
    if pos == "noun" and is_short(correct):
        priority_score += 15
        priority_reasons.append("noun_short_answer")
    if freq_rank is not None:
        if int(freq_rank) <= 1000:
            priority_score += 25
            priority_reasons.append("freq<=1k")
        elif int(freq_rank) <= 2000:
            priority_score += 20
            priority_reasons.append("freq<=2k")
        elif int(freq_rank) <= 5000:
            priority_score += 10
            priority_reasons.append("freq<=5k")

    suggested_wave = "wave_c_tail"
    if source_family == "pilot_safe" and bin_name in {"1K", "2K"}:
        suggested_wave = "wave_a_pilot_safe_1k2k"
    elif source_family == "enriched_qc" and bin_name in {"1K", "2K", "5K"}:
        suggested_wave = "wave_b_enriched_hot"
    elif source_family == "pilot_safe":
        suggested_wave = "wave_b_pilot_safe_rest"

    operator_hint = "review_pack"
    if is_short(correct) and source_family == "pilot_safe" and bin_name in {"1K", "2K"}:
        operator_hint = "review_pack_or_deactivate"
    elif lemma.lower() in FUNCTIONISH:
        operator_hint = "semantic_review_first"

    pack.append({
        "item_pk": item_pk,
        "lemma": lemma,
        "correct_answer": correct,
        "pos": pos,
        "topic_tag": topic_tag,
        "bin_name": bin_name,
        "freq_rank": freq_rank,
        "active_value": row["active_value"],
        "source_family": source_family,
        "priority_score": priority_score,
        "suggested_wave": suggested_wave,
        "operator_hint": operator_hint,
        "priority_reasons": "|".join(priority_reasons),
        "choice_count": len(choices),
        "choices_preview": " || ".join(choices[:8]),
    })

pack.sort(key=lambda r: (
    {"wave_a_pilot_safe_1k2k": 0, "wave_b_enriched_hot": 1, "wave_b_pilot_safe_rest": 2, "wave_c_tail": 3}.get(r["suggested_wave"], 9),
    -int(r["priority_score"]),
    10**9 if r["freq_rank"] is None else int(r["freq_rank"]),
    r["lemma"],
))

cols = [
    "item_pk", "lemma", "correct_answer", "pos", "topic_tag", "bin_name", "freq_rank",
    "active_value", "source_family", "priority_score", "suggested_wave", "operator_hint",
    "priority_reasons", "choice_count", "choices_preview"
]

def write_csv(name: str, rows: list[dict]) -> None:
    with (OUT_DIR / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in cols})

write_csv("legacy_manual_review_full.csv", pack)
write_csv("legacy_manual_review_wave_a_pilot_safe_1k2k.csv", [r for r in pack if r["suggested_wave"] == "wave_a_pilot_safe_1k2k"])
write_csv("legacy_manual_review_wave_b_enriched_hot.csv", [r for r in pack if r["suggested_wave"] == "wave_b_enriched_hot"])
write_csv("legacy_manual_review_wave_b_pilot_safe_rest.csv", [r for r in pack if r["suggested_wave"] == "wave_b_pilot_safe_rest"])
write_csv("legacy_manual_review_wave_c_tail.csv", [r for r in pack if r["suggested_wave"] == "wave_c_tail"])
write_csv("legacy_manual_review_top40.csv", pack[:40])

summary = {
    "db": str(DB),
    "input_csv": str(IN_CSV),
    "rows_total": len(pack),
    "wave_counts": dict(Counter(r["suggested_wave"] for r in pack).most_common()),
    "source_family_counts": dict(Counter(r["source_family"] for r in pack).most_common()),
    "operator_hint_counts": dict(Counter(r["operator_hint"] for r in pack).most_common()),
    "bin_counts": dict(Counter(r["bin_name"] or "EMPTY" for r in pack).most_common()),
    "utc_timestamp": datetime.now(UTC).isoformat(),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT_DIR / "top40.json").write_text(json.dumps(pack[:40], ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(summary, ensure_ascii=False, indent=2))
print("\nTOP40")
for r in pack[:40]:
    print(json.dumps(r, ensure_ascii=False))
conn.close()
