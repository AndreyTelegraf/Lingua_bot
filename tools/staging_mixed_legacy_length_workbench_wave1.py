from __future__ import annotations
import csv
import json
import sqlite3
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
AUTO_DIR = ROOT / "data/master_source_v1/processed/staging_review_autocluster_wave1"
IN_CSV = AUTO_DIR / "review_autocluster_uncategorized.csv"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_mixed_legacy_length_workbench_wave1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not DB.exists():
    raise SystemExit(f"DB not found: {DB}")
if not IN_CSV.exists():
    raise SystemExit(f"Missing input CSV: {IN_CSV}")

with IN_CSV.open("r", encoding="utf-8-sig", newline="") as f:
    src_rows = list(csv.DictReader(f))

if not src_rows:
    raise SystemExit("Input CSV is empty")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

table_info = [dict(r) for r in cur.execute("PRAGMA table_info(vocab_items)").fetchall()]
col_names = [r["name"] for r in table_info]
pk_col = next((r["name"] for r in table_info if int(r["pk"]) == 1), None) or ("id" if "id" in col_names else "item_id")
active_col = "is_active" if "is_active" in col_names else "active"

choice_cols = [dict(r) for r in cur.execute("PRAGMA table_info(vocab_choices)").fetchall()]
choice_col_names = [r["name"] for r in choice_cols]
choice_item_col = "item_id" if "item_id" in choice_col_names else None
choice_text_col = "choice_text" if "choice_text" in choice_col_names else None
choice_pos_col = "position_index" if "position_index" in choice_col_names else None
choice_correct_col = "is_correct" if "is_correct" in choice_col_names else None
if not choice_item_col or not choice_text_col:
    raise SystemExit("Could not detect vocab_choices shape")

FUNCTIONISH = {
    "agora", "ainda", "já", "ja", "só", "so", "nem", "também", "tambem",
    "senão", "senao", "todo", "toda", "todos", "todas", "boa", "bom",
    "última", "ultima", "último", "ultimo", "único", "unico", "única", "unica",
    "bastante"
}
GENERIC_BAD_CHOICES = {"часть", "форма", "случай", "вопрос", "ответ", "раз", "день", "год", "ночь", "время"}
GOOD_KEEP_SOURCES = {"safe_promote", "openwordnet"}
LEGACY_SOURCES = {"pilot_safe", "enriched_qc", "kaikki"}

def norm(x) -> str:
    return "" if x is None else str(x).strip()

def load_choices(item_id: int) -> list[dict]:
    sql = f"SELECT * FROM vocab_choices WHERE {choice_item_col} = ?"
    if choice_pos_col:
        sql += f" ORDER BY {choice_pos_col}"
    rows = [dict(r) for r in cur.execute(sql, (item_id,)).fetchall()]
    out = []
    for r in rows:
        out.append({
            "choice_text": norm(r.get(choice_text_col)),
            "is_correct": r.get(choice_correct_col),
            "position_index": r.get(choice_pos_col),
        })
    return out

def is_multiword(text: str) -> bool:
    return len(text.split()) >= 2

def short_answer(text: str) -> bool:
    return len(text) <= 4

def generic_choice_ratio(choices: list[str]) -> float:
    if not choices:
        return 0.0
    bad = sum(1 for c in choices if c in GENERIC_BAD_CHOICES)
    return bad / len(choices)

def classify(row_db: dict, src: dict, choices: list[str]) -> tuple[str, str, list[str]]:
    lemma = norm(row_db.get("lemma")).lower()
    correct = norm(row_db.get("correct_answer"))
    source_family = norm(src.get("source_family"))
    pos = norm(row_db.get("pos")).lower()

    reasons = []
    if lemma in FUNCTIONISH:
        reasons.append("functionish_lemma")
    if is_multiword(correct):
        reasons.append("multiword_answer")
    if short_answer(correct):
        reasons.append("short_correct")
    if generic_choice_ratio(choices) >= 0.5:
        reasons.append("generic_choice_pack")
    if source_family in LEGACY_SOURCES:
        reasons.append("legacy_source_family")
    if pos == "noun" and lemma in FUNCTIONISH:
        reasons.append("noun_function_word_surface")

    auto_bucket = "manual_tail"
    action = "manual_review"

    if "generic_choice_pack" in reasons and source_family in LEGACY_SOURCES:
        auto_bucket = "auto_deactivate_legacy_generic"
        action = "deactivate"
    elif "noun_function_word_surface" in reasons:
        auto_bucket = "auto_deactivate_surface"
        action = "deactivate"
    elif "multiword_answer" in reasons and source_family in LEGACY_SOURCES:
        auto_bucket = "repair_or_deactivate_legacy_phrase"
        action = "repair_or_deactivate"
    elif "generic_choice_pack" in reasons:
        auto_bucket = "repair_generic_pack"
        action = "repair_or_deactivate"
    elif source_family in GOOD_KEEP_SOURCES:
        auto_bucket = "keep_for_manual_repair"
        action = "manual_repair"
    elif source_family in LEGACY_SOURCES:
        auto_bucket = "legacy_manual_review"
        action = "manual_review"

    return auto_bucket, action, reasons

workbench = []
for src in src_rows:
    item_pk = int(src["item_pk"])
    row = cur.execute(
        f"SELECT {pk_col} AS item_pk, lemma, correct_answer, pos, topic_tag, bin_name, freq_rank, {active_col} AS active_value FROM vocab_items WHERE {pk_col} = ?",
        (item_pk,),
    ).fetchone()
    if row is None:
        continue
    row = dict(row)
    choices_raw = load_choices(item_pk)
    choices = []
    seen = set()
    for ch in choices_raw:
        txt = ch["choice_text"]
        if txt and txt not in seen:
            choices.append(txt)
            seen.add(txt)

    auto_bucket, action, reasons = classify(row, src, choices)

    workbench.append({
        "item_pk": item_pk,
        "lemma": norm(row.get("lemma")),
        "correct_answer": norm(row.get("correct_answer")),
        "pos": norm(row.get("pos")),
        "topic_tag": norm(row.get("topic_tag")),
        "bin_name": norm(row.get("bin_name")),
        "freq_rank": row.get("freq_rank"),
        "active_value": row.get("active_value"),
        "source_family": norm(src.get("source_family")),
        "primary_flag": norm(src.get("primary_flag")),
        "auto_bucket": auto_bucket,
        "suggested_action": action,
        "reason_codes": "|".join(reasons),
        "choice_count": len(choices),
        "generic_choice_ratio": round(generic_choice_ratio(choices), 3),
        "choices_preview": " || ".join(choices[:8]),
    })

bucket_order = {
    "auto_deactivate_legacy_generic": 0,
    "auto_deactivate_surface": 1,
    "repair_or_deactivate_legacy_phrase": 2,
    "repair_generic_pack": 3,
    "keep_for_manual_repair": 4,
    "legacy_manual_review": 5,
    "manual_tail": 6,
}
workbench.sort(key=lambda r: (
    bucket_order.get(r["auto_bucket"], 9),
    10**9 if r["freq_rank"] is None else int(r["freq_rank"]),
    r["lemma"],
))

cols = [
    "item_pk", "lemma", "correct_answer", "pos", "topic_tag", "bin_name", "freq_rank",
    "active_value", "source_family", "primary_flag", "auto_bucket", "suggested_action",
    "reason_codes", "choice_count", "generic_choice_ratio", "choices_preview"
]

def write_csv(name: str, predicate):
    path = OUT_DIR / name
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in workbench:
            if predicate(r):
                w.writerow({k: r.get(k) for k in cols})

write_csv("mixed_workbench_full.csv", lambda r: True)
write_csv("mixed_auto_deactivate_legacy_generic.csv", lambda r: r["auto_bucket"] == "auto_deactivate_legacy_generic")
write_csv("mixed_auto_deactivate_surface.csv", lambda r: r["auto_bucket"] == "auto_deactivate_surface")
write_csv("mixed_repair_or_deactivate_legacy_phrase.csv", lambda r: r["auto_bucket"] == "repair_or_deactivate_legacy_phrase")
write_csv("mixed_repair_generic_pack.csv", lambda r: r["auto_bucket"] == "repair_generic_pack")
write_csv("mixed_keep_for_manual_repair.csv", lambda r: r["auto_bucket"] == "keep_for_manual_repair")
write_csv("mixed_legacy_manual_review.csv", lambda r: r["auto_bucket"] == "legacy_manual_review")
write_csv("mixed_manual_tail.csv", lambda r: r["auto_bucket"] == "manual_tail")

summary = {
    "db": str(DB),
    "input_csv": str(IN_CSV),
    "rows_total": len(workbench),
    "bucket_counts": dict(Counter(r["auto_bucket"] for r in workbench).most_common()),
    "action_counts": dict(Counter(r["suggested_action"] for r in workbench).most_common()),
    "source_family_counts": dict(Counter(r["source_family"] for r in workbench).most_common()),
    "reason_code_counts": dict(Counter(
        code
        for r in workbench
        for code in (r["reason_codes"].split("|") if r["reason_codes"] else [])
        if code
    ).most_common()),
    "utc_timestamp": datetime.now(UTC).isoformat(),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT_DIR / "top30.json").write_text(json.dumps(workbench[:30], ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(summary, ensure_ascii=False, indent=2))
print("\nTOP30")
for r in workbench[:30]:
    print(json.dumps(r, ensure_ascii=False))
conn.close()
