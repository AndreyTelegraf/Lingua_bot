from __future__ import annotations
import csv
import json
import sqlite3
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_smoke_residual_forensics_v1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not DB.exists():
    raise SystemExit(f"DB not found: {DB}")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def q(sql: str, params=()):
    return [dict(r) for r in cur.execute(sql, params).fetchall()]

def one(sql: str, params=()):
    r = cur.execute(sql, params).fetchone()
    return dict(r) if r is not None else None

def table_exists(name: str) -> bool:
    r = cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return r is not None

def cols(table: str) -> list[str]:
    return [r["name"] for r in q(f"PRAGMA table_info({table})")]

def choose(names: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in names:
            return c
    return None

def norm(x) -> str:
    return "" if x is None else str(x).strip()

surface = {}
tables = [r["name"] for r in q("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
for t in tables:
    surface[t] = {"columns": cols(t)}

required = ["vocab_attempts", "vocab_answers", "vocab_items", "vocab_choices"]
missing = [t for t in required if t not in surface]
if missing:
    raise SystemExit(f"Missing required tables: {missing}")

attempt_cols = surface["vocab_attempts"]["columns"]
answer_cols = surface["vocab_answers"]["columns"]
item_cols = surface["vocab_items"]["columns"]
choice_cols = surface["vocab_choices"]["columns"]

attempt_pk = choose(attempt_cols, ["id", "attempt_id"])
attempt_user = choose(attempt_cols, ["user_id", "telegram_user_id"])
attempt_created = choose(attempt_cols, ["created_at", "started_at", "updated_at"])
attempt_finished = choose(attempt_cols, ["finished_at", "completed_at", "ended_at"])
attempt_mode = choose(attempt_cols, ["mode", "mode_code", "test_type"])
attempt_score = choose(attempt_cols, ["correct_count", "score", "result_score"])

answer_attempt = choose(answer_cols, ["attempt_id"])
answer_item = choose(answer_cols, ["item_id", "vocab_item_id"])
answer_is_correct = choose(answer_cols, ["is_correct", "correct"])
answer_position = choose(answer_cols, ["position_index", "step_index", "question_index", "position"])
answer_selected = choose(answer_cols, ["selected_choice_text", "selected_text", "answer_text", "selected_answer"])
answer_created = choose(answer_cols, ["created_at", "answered_at"])

item_pk = choose(item_cols, ["id", "item_id"])
item_active = choose(item_cols, ["is_active", "active"])
item_lemma = choose(item_cols, ["lemma"])
item_correct = choose(item_cols, ["correct_answer"])
item_pos = choose(item_cols, ["pos"])
item_topic = choose(item_cols, ["topic_tag"])
item_bin = choose(item_cols, ["bin_name"])
item_freq = choose(item_cols, ["freq_rank"])

choice_item = choose(choice_cols, ["item_id", "vocab_item_id"])
choice_text = choose(choice_cols, ["choice_text", "text", "option_text"])
choice_pos = choose(choice_cols, ["position_index", "position", "idx", "sort_order"])
choice_correct = choose(choice_cols, ["is_correct", "correct"])

if not all([attempt_pk, answer_attempt, answer_item, item_pk, choice_item, choice_text]):
    raise SystemExit("Could not detect key schema columns")

attempts_sql = f"SELECT * FROM vocab_attempts ORDER BY {attempt_pk} DESC LIMIT 5"
latest_attempts = q(attempts_sql)
if not latest_attempts:
    raise SystemExit("No vocab_attempts found. Run manual smoke first.")

latest_attempt_id = latest_attempts[0][attempt_pk]

answers_sql = f"""
SELECT a.*, i.{item_lemma} AS lemma, i.{item_correct} AS correct_answer,
       i.{item_pos} AS pos, i.{item_topic} AS topic_tag, i.{item_bin} AS bin_name,
       i.{item_freq} AS freq_rank, i.{item_active} AS item_active
FROM vocab_answers a
JOIN vocab_items i ON i.{item_pk} = a.{answer_item}
WHERE a.{answer_attempt} = ?
"""
if answer_position:
    answers_sql += f" ORDER BY a.{answer_position}"
elif answer_created:
    answers_sql += f" ORDER BY a.{answer_created}"
else:
    answers_sql += f" ORDER BY a.rowid"

attempt_answers = q(answers_sql, (latest_attempt_id,))

def load_choices(item_id: int) -> list[dict]:
    sql = f"SELECT * FROM vocab_choices WHERE {choice_item} = ?"
    if choice_pos:
        sql += f" ORDER BY {choice_pos}"
    rows = q(sql, (item_id,))
    out = []
    for r in rows:
        out.append({
            "choice_text": norm(r.get(choice_text)),
            "is_correct": r.get(choice_correct),
            "position": r.get(choice_pos),
        })
    return out

# candidate heuristics for residual UX dirt
def short_answer(s: str) -> bool:
    return len(norm(s)) <= 4

def multiword(s: str) -> bool:
    return len(norm(s).split()) >= 2

def weird_translation(s: str) -> bool:
    s = norm(s).lower()
    bad = {"око", "ар", "азс", "брутальность", "книшный магазин"}
    return s in bad

def generic_pack(choices: list[str]) -> bool:
    generic = {"часть", "форма", "случай", "вопрос", "ответ"}
    return sum(1 for c in choices if c in generic) >= 2

residual = []
for a in attempt_answers:
    item_id = a[answer_item]
    choices = load_choices(item_id)
    choice_texts = [c["choice_text"] for c in choices if c["choice_text"]]
    rec = {
        "attempt_id": latest_attempt_id,
        "position": a.get(answer_position),
        "item_id": item_id,
        "lemma": norm(a.get("lemma")),
        "correct_answer": norm(a.get("correct_answer")),
        "selected_answer": norm(a.get(answer_selected)) if answer_selected else "",
        "is_correct": a.get(answer_is_correct),
        "pos": norm(a.get("pos")),
        "topic_tag": norm(a.get("topic_tag")),
        "bin_name": norm(a.get("bin_name")),
        "freq_rank": a.get("freq_rank"),
        "item_active": a.get("item_active"),
        "choice_count": len(choice_texts),
        "choices_preview": " || ".join(choice_texts[:8]),
        "flags": [],
    }
    if short_answer(rec["correct_answer"]):
        rec["flags"].append("short_answer")
    if multiword(rec["correct_answer"]):
        rec["flags"].append("multiword_answer")
    if weird_translation(rec["correct_answer"]):
        rec["flags"].append("weird_translation")
    if generic_pack(choice_texts):
        rec["flags"].append("generic_pack")
    if rec["pos"] == "noun" and short_answer(rec["correct_answer"]):
        rec["flags"].append("noun_short_answer")
    if rec["topic_tag"].startswith("build:pilot_ptpt_001_pilot_safe"):
        rec["flags"].append("pilot_safe_source")
    if rec["topic_tag"].startswith("build:pilot_ptpt_001_enriched_qc"):
        rec["flags"].append("enriched_qc_source")
    if rec["flags"]:
        residual.append(rec)

# include recent report events if any
report_events = []
if table_exists("vocab_attempt_events"):
    ev_cols = surface["vocab_attempt_events"]["columns"]
    ev_attempt = choose(ev_cols, ["attempt_id"])
    ev_type = choose(ev_cols, ["event_type", "type"])
    ev_payload = choose(ev_cols, ["payload_json", "payload", "data_json", "data"])
    ev_created = choose(ev_cols, ["created_at", "timestamp"])
    if ev_attempt and ev_type:
        sql = f"SELECT * FROM vocab_attempt_events WHERE {ev_attempt} = ? AND {ev_type} = 'item_reported'"
        if ev_created:
            sql += f" ORDER BY {ev_created} DESC"
        report_events = q(sql, (latest_attempt_id,))

# outputs
summary = {
    "db": str(DB),
    "latest_attempt_id": latest_attempt_id,
    "latest_attempt_meta": {
        "user_id": latest_attempts[0].get(attempt_user) if attempt_user else None,
        "created_at": latest_attempts[0].get(attempt_created) if attempt_created else None,
        "finished_at": latest_attempts[0].get(attempt_finished) if attempt_finished else None,
        "mode": latest_attempts[0].get(attempt_mode) if attempt_mode else None,
        "score": latest_attempts[0].get(attempt_score) if attempt_score else None,
    },
    "answers_in_latest_attempt": len(attempt_answers),
    "residual_flagged_count": len(residual),
    "residual_flag_counts": dict(Counter(flag for r in residual for flag in r["flags"]).most_common()),
    "report_events_count": len(report_events),
    "utc_timestamp": datetime.now(UTC).isoformat(),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT_DIR / "latest_attempt_full.json").write_text(json.dumps(attempt_answers, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT_DIR / "latest_attempt_residual_flagged.json").write_text(json.dumps(residual, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT_DIR / "latest_attempt_report_events.json").write_text(json.dumps(report_events, ensure_ascii=False, indent=2), encoding="utf-8")

csv_cols = [
    "attempt_id", "position", "item_id", "lemma", "correct_answer", "selected_answer", "is_correct",
    "pos", "topic_tag", "bin_name", "freq_rank", "item_active", "choice_count", "flags", "choices_preview"
]
with (OUT_DIR / "latest_attempt_residual_flagged.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=csv_cols)
    w.writeheader()
    for r in residual:
        row = dict(r)
        row["flags"] = "|".join(r["flags"])
        w.writerow({k: row.get(k) for k in csv_cols})

print(json.dumps(summary, ensure_ascii=False, indent=2))
print("\nRESIDUAL_HEAD")
for r in residual[:20]:
    print(json.dumps(r, ensure_ascii=False))
conn.close()
