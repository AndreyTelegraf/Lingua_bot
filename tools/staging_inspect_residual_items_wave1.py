from __future__ import annotations
import json
import sqlite3
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_inspect_residual_items_wave1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_IDS = [57, 3366, 3393]

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def q(sql, params=()):
    return [dict(r) for r in cur.execute(sql, params).fetchall()]

def one(sql, params=()):
    r = cur.execute(sql, params).fetchone()
    return dict(r) if r else None

def cols(table):
    return [r["name"] for r in q(f"PRAGMA table_info({table})")]

item_cols = cols("vocab_items")
choice_cols = cols("vocab_choices")
event_cols = cols("vocab_attempt_events") if one("SELECT name FROM sqlite_master WHERE type='table' AND name='vocab_attempt_events'") else []

item_pk = "id" if "id" in item_cols else "item_id"
item_active = "is_active" if "is_active" in item_cols else "active"

choice_item = "item_id" if "item_id" in choice_cols else "vocab_item_id"
choice_text = "choice_text" if "choice_text" in choice_cols else "text"
choice_pos = "position_index" if "position_index" in choice_cols else None
choice_correct = "is_correct" if "is_correct" in choice_cols else "correct"

out = []
for item_id in TARGET_IDS:
    item = one(f"""
        SELECT
          {item_pk} AS item_id,
          lemma,
          question_text,
          correct_answer,
          pos,
          topic_tag,
          bin_name,
          freq_rank,
          {item_active} AS is_active
        FROM vocab_items
        WHERE {item_pk} = ?
    """, (item_id,))
    choices_sql = f"SELECT {choice_text} AS choice_text, {choice_correct} AS is_correct"
    if choice_pos:
        choices_sql += f", {choice_pos} AS position_index"
    choices_sql += f" FROM vocab_choices WHERE {choice_item} = ?"
    if choice_pos:
        choices_sql += f" ORDER BY {choice_pos}"
    choices = q(choices_sql, (item_id,))

    reports = []
    if event_cols:
        reports = q("""
            SELECT id, attempt_id, user_id, event_type, step_index, item_id, reason_code, payload_json, created_at
            FROM vocab_attempt_events
            WHERE item_id = ? AND event_type = 'item_reported'
            ORDER BY created_at DESC, id DESC
        """, (item_id,))

    out.append({
        "item": item,
        "choices": choices,
        "report_events": reports,
    })

summary = {
    "db": str(DB),
    "target_ids": TARGET_IDS,
    "items_found": len([x for x in out if x["item"]]),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT_DIR / "items_full.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(summary, ensure_ascii=False, indent=2))
for block in out:
    print("\n===== ITEM =====")
    print(json.dumps(block["item"], ensure_ascii=False, indent=2))
    print("----- CHOICES -----")
    print(json.dumps(block["choices"], ensure_ascii=False, indent=2))
    print("----- REPORT EVENTS -----")
    print(json.dumps(block["report_events"], ensure_ascii=False, indent=2))

conn.close()
