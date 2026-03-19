from __future__ import annotations
import csv
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
AUTOCLUSTER_DIR = ROOT / "data/master_source_v1/processed/staging_review_autocluster_wave1"
IN_CSV = AUTOCLUSTER_DIR / "review_autocluster_high.csv"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_high_review_workbench_wave1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not DB.exists():
    raise SystemExit(f"DB not found: {DB}")
if not IN_CSV.exists():
    raise SystemExit(f"Missing input CSV: {IN_CSV}")

def table_info(cur: sqlite3.Cursor, table: str) -> list[dict]:
    return [dict(r) for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]

def all_tables(cur: sqlite3.Cursor) -> list[str]:
    return [r["name"] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]

def sample_rows(cur: sqlite3.Cursor, table: str, limit: int = 3) -> list[dict]:
    try:
        return [dict(r) for r in cur.execute(f"SELECT * FROM {table} LIMIT {limit}").fetchall()]
    except Exception:
        return []

def choose_col(cols: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in cols:
            return c
    return None

def norm(v) -> str:
    return "" if v is None else str(v).strip()

def looks_functionish(lemma: str) -> bool:
    lemma = lemma.lower().strip()
    functionish = {
        "agora", "ainda", "já", "so", "só", "nem", "também", "senão", "ou", "e", "mas",
        "todo", "toda", "todos", "todas", "boa", "bom", "última", "último", "único", "única",
        "bastante", "ir", "são", "tinha"
    }
    return lemma in functionish

def looks_phrase(answer: str) -> bool:
    return len(answer.split()) >= 2

def suspicious_pos_pair(lemma: str, pos: str, answer: str) -> bool:
    pos = pos.lower().strip()
    if pos == "noun" and looks_functionish(lemma):
        return True
    if pos == "noun" and looks_phrase(answer):
        return True
    return False

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

tables = all_tables(cur)
surface = {}
for t in tables:
    cols = [r["name"] for r in table_info(cur, t)]
    surface[t] = {
        "columns": cols,
        "sample_rows": sample_rows(cur, t, limit=2),
    }

# detect vocab_items pk
vocab_cols = [r["name"] for r in table_info(cur, "vocab_items")]
vocab_pk = choose_col(vocab_cols, ["id", "item_id"])
if not vocab_pk:
    raise SystemExit("Could not detect vocab_items PK")

# candidate choice tables
choice_table_candidates = []
for t in tables:
    cols = surface[t]["columns"]
    cols_lower = set(cols)
    if t == "vocab_items":
        continue
    if any(c in cols_lower for c in ("item_id", "vocab_item_id", "question_id", "vocab_question_id")) and \
       any(c in cols_lower for c in ("choice_text", "option_text", "text", "answer_text", "value")):
        choice_table_candidates.append(t)

# candidate metadata/source tables
meta_table_candidates = []
for t in tables:
    cols = surface[t]["columns"]
    cols_lower = set(cols)
    if any(c in cols_lower for c in ("item_id", "vocab_item_id", "question_id", "vocab_question_id")) and \
       any(c in cols_lower for c in ("source_family", "source", "topic_tag", "bin_name", "freq_rank", "pos", "lemma")):
        meta_table_candidates.append(t)

# load high items
with IN_CSV.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

item_ids = [int(r["item_pk"]) for r in rows if norm(r.get("item_pk")).isdigit()]
if not item_ids:
    raise SystemExit("No item ids in review_autocluster_high.csv")

# helper: extract choices by probing candidate tables
def fetch_choices_for_item(item_id: int) -> list[dict]:
    out: list[dict] = []
    for t in choice_table_candidates:
        cols = surface[t]["columns"]
        item_col = choose_col(cols, ["item_id", "vocab_item_id", "question_id", "vocab_question_id"])
        choice_col = choose_col(cols, ["choice_text", "option_text", "text", "answer_text", "value"])
        sort_col = choose_col(cols, ["position", "sort_order", "idx", "choice_index", "id"])
        is_correct_col = choose_col(cols, ["is_correct", "correct", "is_right"])
        if not item_col or not choice_col:
            continue
        sql = f"SELECT * FROM {t} WHERE {item_col} = ?"
        if sort_col:
            sql += f" ORDER BY {sort_col}"
        try:
            fetched = [dict(r) for r in cur.execute(sql, (item_id,)).fetchall()]
        except Exception:
            continue
        for r in fetched:
            out.append({
                "table": t,
                "item_col": item_col,
                "choice_text": norm(r.get(choice_col)),
                "is_correct": r.get(is_correct_col) if is_correct_col else None,
                "raw": r,
            })
    return out

# helper: extract related rows from metadata tables
def fetch_meta_for_item(item_id: int) -> list[dict]:
    out: list[dict] = []
    for t in meta_table_candidates:
        cols = surface[t]["columns"]
        item_col = choose_col(cols, ["item_id", "vocab_item_id", "question_id", "vocab_question_id"])
        if not item_col:
            continue
        try:
            fetched = [dict(r) for r in cur.execute(f"SELECT * FROM {t} WHERE {item_col} = ?", (item_id,)).fetchall()]
        except Exception:
            continue
        for r in fetched:
            out.append({"table": t, "item_col": item_col, "raw": r})
    return out

workbench_rows = []
for src in rows:
    item_id = int(src["item_pk"])
    item = cur.execute(
        f"SELECT * FROM vocab_items WHERE {vocab_pk} = ?",
        (item_id,),
    ).fetchone()
    if not item:
        continue
    item = dict(item)
    lemma = norm(item.get("lemma"))
    pos = norm(item.get("pos"))
    correct_answer = norm(item.get("correct_answer"))
    choices = fetch_choices_for_item(item_id)
    meta = fetch_meta_for_item(item_id)

    unique_choices = []
    seen = set()
    for ch in choices:
        txt = ch["choice_text"]
        if txt and txt not in seen:
            unique_choices.append(txt)
            seen.add(txt)

    has_choices = bool(unique_choices)
    correct_in_choices = correct_answer in seen if has_choices else None
    phrase_answer = looks_phrase(correct_answer)
    funcish = looks_functionish(lemma)
    susp = suspicious_pos_pair(lemma, pos, correct_answer)

    suggested_action = "manual_review"
    auto_bucket = "needs_human"
    reasons = []

    if not has_choices:
        reasons.append("no_choice_pack_found")
    if correct_in_choices is False:
        reasons.append("correct_not_in_choices_live")
    if funcish:
        reasons.append("functionish_lemma")
    if phrase_answer:
        reasons.append("multiword_answer")
    if susp:
        reasons.append("suspicious_pos_or_surface")

    if ("no_choice_pack_found" in reasons and "suspicious_pos_or_surface" in reasons) or \
       ("correct_not_in_choices_live" in reasons):
        suggested_action = "candidate_deactivate"
        auto_bucket = "auto_deactivate_candidate"
    elif "no_choice_pack_found" in reasons or "multiword_answer" in reasons:
        suggested_action = "candidate_repair_or_deactivate"
        auto_bucket = "repair_first"
    elif "suspicious_pos_or_surface" in reasons:
        suggested_action = "candidate_manual_semantic_review"
        auto_bucket = "semantic_review"

    workbench_rows.append({
        "item_pk": item_id,
        "lemma": lemma,
        "correct_answer": correct_answer,
        "pos": pos,
        "topic_tag": norm(item.get("topic_tag")),
        "bin_name": norm(item.get("bin_name")),
        "freq_rank": item.get("freq_rank"),
        "is_active": item.get("is_active"),
        "high_cluster": norm(src.get("human_cluster")),
        "source_family": norm(src.get("source_family")),
        "has_choices": has_choices,
        "choice_count_unique": len(unique_choices),
        "correct_in_choices": correct_in_choices,
        "functionish_lemma": funcish,
        "multiword_answer": phrase_answer,
        "suspicious_pos_or_surface": susp,
        "auto_bucket": auto_bucket,
        "suggested_action": suggested_action,
        "reason_codes": "|".join(reasons),
        "choices_preview": " || ".join(unique_choices[:8]),
        "meta_tables_hit": "|".join(sorted({m['table'] for m in meta})),
    })

# outputs
workbench_rows_sorted = sorted(
    workbench_rows,
    key=lambda r: (
        {"auto_deactivate_candidate": 0, "repair_first": 1, "semantic_review": 2, "needs_human": 3}.get(r["auto_bucket"], 9),
        10**9 if r["freq_rank"] is None else int(r["freq_rank"]),
        r["lemma"],
    ),
)

cols = [
    "item_pk", "lemma", "correct_answer", "pos", "topic_tag", "bin_name", "freq_rank",
    "is_active", "high_cluster", "source_family",
    "has_choices", "choice_count_unique", "correct_in_choices",
    "functionish_lemma", "multiword_answer", "suspicious_pos_or_surface",
    "auto_bucket", "suggested_action", "reason_codes", "choices_preview", "meta_tables_hit"
]

for name, predicate in {
    "high_review_workbench_full.csv": lambda r: True,
    "high_review_auto_deactivate_candidates.csv": lambda r: r["auto_bucket"] == "auto_deactivate_candidate",
    "high_review_repair_first.csv": lambda r: r["auto_bucket"] == "repair_first",
    "high_review_semantic_review.csv": lambda r: r["auto_bucket"] == "semantic_review",
}.items():
    with (OUT_DIR / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in workbench_rows_sorted:
            if predicate(r):
                w.writerow({k: r.get(k) for k in cols})

summary = {
    "db": str(DB),
    "input_csv": str(IN_CSV),
    "rows_total": len(workbench_rows_sorted),
    "choice_table_candidates": choice_table_candidates,
    "meta_table_candidates": meta_table_candidates,
    "auto_bucket_counts": dict(Counter(r["auto_bucket"] for r in workbench_rows_sorted).most_common()),
    "suggested_action_counts": dict(Counter(r["suggested_action"] for r in workbench_rows_sorted).most_common()),
    "reason_code_counts": dict(Counter(
        reason for r in workbench_rows_sorted for reason in (r["reason_codes"].split("|") if r["reason_codes"] else [])
    ).most_common()),
    "utc_timestamp": datetime.now(UTC).isoformat(),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

schema_probe = {
    "tables": tables,
    "choice_table_candidates": {t: surface[t] for t in choice_table_candidates},
    "meta_table_candidates": {t: surface[t] for t in meta_table_candidates},
}
(OUT_DIR / "schema_probe.json").write_text(json.dumps(schema_probe, ensure_ascii=False, indent=2), encoding="utf-8")

top_rows = workbench_rows_sorted[:25]
(OUT_DIR / "top25.json").write_text(json.dumps(top_rows, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(summary, ensure_ascii=False, indent=2))
print("\nTOP25")
for r in top_rows:
    print(json.dumps(r, ensure_ascii=False))
