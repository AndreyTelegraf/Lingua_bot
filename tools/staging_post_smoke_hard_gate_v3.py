from __future__ import annotations
import csv
import json
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_post_smoke_hard_gate_v3"
OUT_DIR.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def table_cols(table: str) -> list[str]:
    return [r["name"] for r in cur.execute(f"PRAGMA table_info({table})")]

vocab_item_cols = table_cols("vocab_items")
attempt_cols = table_cols("vocab_attempts")
answer_cols = table_cols("vocab_answers")
event_cols = table_cols("vocab_attempt_events")

active_col = "is_active" if "is_active" in vocab_item_cols else "active"

attempt_parts = ["id"]
attempt_parts.append("user_id" if "user_id" in attempt_cols else "NULL AS user_id")
attempt_parts.append("created_at" if "created_at" in attempt_cols else "NULL AS created_at")
attempt_parts.append("finished_at" if "finished_at" in attempt_cols else "NULL AS finished_at")
attempt_parts.append("mode" if "mode" in attempt_cols else "NULL AS mode")
attempt_parts.append("score" if "score" in attempt_cols else "NULL AS score")

latest_attempt = cur.execute(
    f"SELECT {', '.join(attempt_parts)} FROM vocab_attempts ORDER BY id DESC LIMIT 1"
).fetchone()
if latest_attempt is None:
    raise SystemExit("No attempts found in staging DB")

latest_attempt_id = int(latest_attempt["id"])

report_rows = []
if set(["attempt_id", "event_type", "item_id"]).issubset(event_cols):
    report_select = [
        "id" if "id" in event_cols else "NULL AS id",
        "attempt_id",
        "user_id" if "user_id" in event_cols else "NULL AS user_id",
        "event_type",
        "step_index" if "step_index" in event_cols else "NULL AS step_index",
        "item_id",
        "reason_code" if "reason_code" in event_cols else "NULL AS reason_code",
        "payload_json" if "payload_json" in event_cols else "NULL AS payload_json",
        "created_at" if "created_at" in event_cols else "NULL AS created_at",
    ]
    report_rows = cur.execute(
        f"""
        SELECT {', '.join(report_select)}
        FROM vocab_attempt_events
        WHERE attempt_id = ?
          AND event_type = 'item_reported'
        ORDER BY item_id, id
        """,
        (latest_attempt_id,),
    ).fetchall()

report_item_ids = sorted({int(r["item_id"]) for r in report_rows if r["item_id"] is not None})

if not set(["attempt_id", "item_id"]).issubset(answer_cols):
    raise SystemExit("vocab_answers schema missing attempt_id/item_id")

answer_parts = [
    "va.attempt_id",
    "va.item_id",
    "vi.id AS item_pk",
    "vi.lemma",
    "COALESCE(vi.question_text, vi.lemma) AS question_text" if "question_text" in vocab_item_cols else "vi.lemma AS question_text",
    "vi.correct_answer",
    "vi.pos" if "pos" in vocab_item_cols else "NULL AS pos",
    "vi.topic_tag" if "topic_tag" in vocab_item_cols else "NULL AS topic_tag",
    "vi.bin_name" if "bin_name" in vocab_item_cols else "NULL AS bin_name",
    "vi.freq_rank" if "freq_rank" in vocab_item_cols else "NULL AS freq_rank",
    f"vi.{active_col} AS active_value",
]

answer_rows = cur.execute(
    f"""
    SELECT {', '.join(answer_parts)}
    FROM vocab_answers va
    JOIN vocab_items vi ON vi.id = va.item_id
    WHERE va.attempt_id = ?
    ORDER BY vi.id
    """,
    (latest_attempt_id,),
).fetchall()

choice_cols = table_cols("vocab_choices")
choice_order = []
if "position_index" in choice_cols:
    choice_order.append("position_index")
if "id" in choice_cols:
    choice_order.append("id")
choice_order_sql = ", ".join(choice_order) if choice_order else "rowid"

def get_choices(item_id: int):
    select_cols = [
        "choice_text" if "choice_text" in choice_cols else "NULL AS choice_text",
        "is_correct" if "is_correct" in choice_cols else "NULL AS is_correct",
        "position_index" if "position_index" in choice_cols else "NULL AS position_index",
    ]
    return cur.execute(
        f"""
        SELECT {', '.join(select_cols)}
        FROM vocab_choices
        WHERE item_id = ?
        ORDER BY {choice_order_sql}
        """,
        (item_id,),
    ).fetchall()

def source_family(topic_tag: str | None) -> str:
    if not topic_tag:
        return "empty"
    t = str(topic_tag).lower()
    if "pilot_safe" in t:
        return "pilot_safe"
    if "enriched_qc" in t:
        return "enriched_qc"
    if "safe_promote" in t:
        return "safe_promote"
    if "openwordnet" in t:
        return "openwordnet"
    if "kaikki" in t:
        return "kaikki"
    if "adverb_curated" in t:
        return "adverb_curated"
    return "other"

def is_short(text: str | None) -> bool:
    return bool(text and len(text.strip()) <= 5)

def is_multiword(text: str | None) -> bool:
    if not text:
        return False
    t = text.strip()
    return (" " in t) or ("-" in t and len(t) > 4)

functionish_lemmas = {
    "bem", "mal", "já", "ainda", "logo", "nem", "todo", "tudo",
    "mais", "menos", "só", "mesmo", "senão", "outrora",
}

inspection = []
for row in answer_rows:
    item_id = int(row["item_id"])
    correct = (row["correct_answer"] or "").strip()
    pos = row["pos"] or ""
    sf = source_family(row["topic_tag"])
    choices = get_choices(item_id)
    choice_texts = [str(c["choice_text"]) for c in choices if c["choice_text"] is not None]

    flags = []
    if item_id in report_item_ids:
        flags.append("user_reported_in_latest_attempt")
    if sf in {"pilot_safe", "enriched_qc", "kaikki", "adverb_curated"}:
        flags.append(f"{sf}_source")
    if is_short(correct):
        flags.append("short_answer")
    if pos == "noun" and is_short(correct):
        flags.append("noun_short_answer")
    if pos in {"adverb", "adjective"} and is_short(correct):
        flags.append("short_adjadv_answer")
    if is_multiword(correct):
        flags.append("multiword_answer")
    if str(row["lemma"] or "").strip().lower() in functionish_lemmas:
        flags.append("functionish_lemma")

    hard_reasons = []
    should_deactivate = False

    if item_id in report_item_ids:
        should_deactivate = True
        hard_reasons.append("reported_by_user")

    if pos in {"adverb", "adjective"} and is_short(correct):
        should_deactivate = True
        hard_reasons.append("short_adjadv_answer")

    if pos == "noun" and is_short(correct) and sf == "pilot_safe":
        freq = row["freq_rank"] if row["freq_rank"] is not None else 10**9
        if int(freq) <= 2500:
            should_deactivate = True
            hard_reasons.append("pilot_safe_hot_short_noun")

    if "functionish_lemma" in flags and pos in {"adverb", "adjective", "noun"}:
        should_deactivate = True
        hard_reasons.append("functionish_surface")

    inspection.append({
        "item_id": item_id,
        "lemma": row["lemma"],
        "correct_answer": row["correct_answer"],
        "pos": pos,
        "topic_tag": row["topic_tag"],
        "bin_name": row["bin_name"],
        "freq_rank": row["freq_rank"],
        "active_value": row["active_value"],
        "source_family": sf,
        "flags": "|".join(flags),
        "hard_reasons": "|".join(hard_reasons),
        "should_deactivate": 1 if should_deactivate else 0,
        "choices_preview": " || ".join(choice_texts),
    })

inspection.sort(key=lambda x: (-x["should_deactivate"], x["freq_rank"] if x["freq_rank"] is not None else 10**9, x["item_id"]))

(OUT_DIR / "latest_attempt_hard_gate_full.json").write_text(
    json.dumps(inspection, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

with (OUT_DIR / "latest_attempt_hard_gate_candidates.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "item_id", "lemma", "correct_answer", "pos", "topic_tag", "bin_name",
            "freq_rank", "active_value", "source_family", "flags",
            "hard_reasons", "should_deactivate", "choices_preview"
        ],
    )
    writer.writeheader()
    writer.writerows(inspection)

targets = [r for r in inspection if r["should_deactivate"] == 1 and int(r["active_value"]) == 1]
target_ids = [int(r["item_id"]) for r in targets]

backup_path = None
after_rows = []
if target_ids:
    backup_path = OUT_DIR / f"lingua_staging.before_post_smoke_hard_gate_v3.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.db"
    shutil.copy2(DB, backup_path)
    qmarks = ",".join("?" for _ in target_ids)
    cur.execute(f"UPDATE vocab_items SET {active_col}=0 WHERE id IN ({qmarks})", target_ids)
    conn.commit()
    after_rows = [dict(r) for r in cur.execute(
        f"SELECT id AS item_id, lemma, correct_answer, {active_col} AS active_value FROM vocab_items WHERE id IN ({qmarks}) ORDER BY id",
        target_ids,
    ).fetchall()]

active_total_after = cur.execute(f"SELECT COUNT(*) AS c FROM vocab_items WHERE {active_col}=1").fetchone()["c"]

summary = {
    "db": str(DB),
    "latest_attempt_id": latest_attempt_id,
    "latest_attempt_meta": dict(latest_attempt),
    "answers_in_latest_attempt": len(answer_rows),
    "report_events_count": len(report_rows),
    "inspection_count": len(inspection),
    "candidate_count": len(targets),
    "target_ids": target_ids,
    "reason_counts": dict(Counter(reason for r in targets for reason in r["hard_reasons"].split("|") if reason)),
    "source_family_counts": dict(Counter(r["source_family"] for r in targets)),
    "backup": str(backup_path) if backup_path else None,
    "after": after_rows,
    "active_total_after": active_total_after,
    "utc_timestamp": datetime.now(timezone.utc).isoformat(),
}
(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

with (OUT_DIR / "deactivated_items.csv").open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "item_id", "lemma", "correct_answer", "pos", "topic_tag", "bin_name",
            "freq_rank", "source_family", "flags", "hard_reasons", "choices_preview"
        ],
    )
    writer.writeheader()
    for r in targets:
        writer.writerow({
            "item_id": r["item_id"],
            "lemma": r["lemma"],
            "correct_answer": r["correct_answer"],
            "pos": r["pos"],
            "topic_tag": r["topic_tag"],
            "bin_name": r["bin_name"],
            "freq_rank": r["freq_rank"],
            "source_family": r["source_family"],
            "flags": r["flags"],
            "hard_reasons": r["hard_reasons"],
            "choices_preview": r["choices_preview"],
        })

print(json.dumps(summary, ensure_ascii=False, indent=2))
conn.close()
