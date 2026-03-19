from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB_PATH = ROOT / "data/lingua_staging.db"

RAW_JSONL = ROOT / "data/community_waves/wave_v4_raw/community_replenishment_wave_v3.jsonl"
WAVE_V4_DIR = ROOT / "data/community_waves/wave_v4"
REVIEW_V4_DIR = ROOT / "data/community_review/review_pack_v4"

OUT_JSONL = WAVE_V4_DIR / "community_replenishment_wave_v4_constrained.jsonl"
OUT_TSV = WAVE_V4_DIR / "community_replenishment_wave_v4_constrained.tsv"
OUT_REVIEW_TSV = REVIEW_V4_DIR / "community_review_pack_v4.tsv"
OUT_SUMMARY = REVIEW_V4_DIR / "community_review_pack_v4_summary.json"

TARGET_COUNT = 16
MAX_PER_TOPIC = 3
MAX_PER_FORMAT = 8
MAX_FINAL_FIRST1_SHARE = 0.25

PRIORITY_FIRST1 = {"в", "чем", "какими", "какой", "какая", "о"}
PRIORITY_FIRST2 = {
    "в какой",
    "чем в",
    "чем люди",
    "какими словами",
    "какой вариант",
    "какая фраза",
    "о чём",
}
DEPRIORITIZED_FIRST1 = {"как", "что"}
DEPRIORITIZED_FIRST2 = {"что обычно"}

TOPIC_PRIORITY = [
    "culture",
    "work",
    "services",
    "health",
    "financas",
    "food",
    "shopping",
    "transport",
    "documents",
    "bureaucracy",
    "housing",
]

FORMAT_PRIORITY = ["nuance", "dialogue", "local"]

def toks(s: str) -> list[str]:
    return re.findall(r"[^\W_]+", (s or "").lower(), flags=re.UNICODE)

def first1(s: str) -> str:
    t = toks(s)
    return " ".join(t[:1]) if len(t) >= 1 else ""

def first2(s: str) -> str:
    t = toks(s)
    return " ".join(t[:2]) if len(t) >= 2 else ""

def load_live_bank():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, text, format_type, topic
        FROM community_content_items
        WHERE is_active = 1
        ORDER BY id
    """).fetchall()
    conn.close()
    return rows

def load_raw_jsonl(path: Path):
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items

def topic_rank(topic: str) -> int:
    try:
        return TOPIC_PRIORITY.index(topic or "")
    except ValueError:
        return len(TOPIC_PRIORITY) + 1

def format_rank(fmt: str) -> int:
    try:
        return FORMAT_PRIORITY.index(fmt or "")
    except ValueError:
        return len(FORMAT_PRIORITY) + 1

def score_candidate(item: dict, live_topic: Counter, live_format: Counter) -> tuple:
    text = item.get("text", "").strip()
    f1 = first1(text)
    f2 = first2(text)
    topic = (item.get("topic") or "").strip()
    fmt = (item.get("format_type") or "").strip()

    score = 0

    if f1 in PRIORITY_FIRST1:
        score += 35
    if f2 in PRIORITY_FIRST2:
        score += 35

    if f2 in DEPRIORITIZED_FIRST2:
        score -= 60
    if f1 == "что":
        score -= 35
    if f1 == "как":
        score -= 45

    score += max(0, 6 - live_topic.get(topic, 0)) * 5
    score += max(0, 6 - live_format.get(fmt, 0)) * 3

    if len(text) < 80:
        score -= 10
    if len(text) > 210:
        score -= 8

    return (
        -score,
        topic_rank(topic),
        format_rank(fmt),
        len(text),
        text,
    )

def main():
    WAVE_V4_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_V4_DIR.mkdir(parents=True, exist_ok=True)

    if not RAW_JSONL.exists():
        raise SystemExit(f"Raw source missing: {RAW_JSONL}")

    live_rows = load_live_bank()
    raw_items = load_raw_jsonl(RAW_JSONL)

    live_texts = {r["text"].strip() for r in live_rows}
    live_first1 = Counter(first1(r["text"]) for r in live_rows)
    live_topic = Counter((r["topic"] or "").strip() for r in live_rows)
    live_format = Counter((r["format_type"] or "").strip() for r in live_rows)

    final_total = len(live_rows) + len(raw_items)
    merged_first1_cap = int(MAX_FINAL_FIRST1_SHARE * final_total)
    if merged_first1_cap < 1:
        merged_first1_cap = 1

    dedup_seen = set()
    filtered = []

    for item in raw_items:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        if text in live_texts:
            continue
        if text in dedup_seen:
            continue
        dedup_seen.add(text)
        filtered.append(item)

    filtered.sort(key=lambda x: score_candidate(x, live_topic, live_format))

    selected = []
    sel_first1 = Counter()
    sel_topic = Counter()
    sel_format = Counter()
    rejected_by_cap = []

    for item in filtered:
        text = item.get("text", "").strip()
        f1 = first1(text)
        topic = (item.get("topic") or "").strip()
        fmt = (item.get("format_type") or "").strip()

        merged_if_add = live_first1[f1] + sel_first1[f1] + 1
        if merged_if_add > merged_first1_cap:
            rejected_by_cap.append({
                "reason": "merged_first1_cap",
                "first1": f1,
                "live_count": live_first1[f1],
                "selected_count": sel_first1[f1],
                "cap": merged_first1_cap,
                "text": text,
            })
            continue

        if sel_topic[topic] >= MAX_PER_TOPIC:
            continue
        if sel_format[fmt] >= MAX_PER_FORMAT:
            continue

        selected.append(item)
        sel_first1[f1] += 1
        sel_topic[topic] += 1
        sel_format[fmt] += 1

        if len(selected) >= TARGET_COUNT:
            break

    with OUT_JSONL.open("w", encoding="utf-8") as f:
        for item in selected:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with OUT_TSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["scenario_id", "opening_family", "context", "intent", "format_type", "topic", "text"])
        for item in selected:
            w.writerow([
                item.get("scenario_id", ""),
                item.get("opening_family", ""),
                item.get("context", ""),
                item.get("intent", ""),
                item.get("format_type", ""),
                item.get("topic", ""),
                item.get("text", ""),
            ])

    with OUT_REVIEW_TSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["scenario_id", "topic", "format_type", "opening_family", "context", "intent", "review_action", "review_note", "text"])
        for item in selected:
            w.writerow([
                item.get("scenario_id", ""),
                item.get("topic", ""),
                item.get("format_type", ""),
                item.get("opening_family", ""),
                item.get("context", ""),
                item.get("intent", ""),
                "",
                "",
                item.get("text", ""),
            ])

    merged_projection = Counter(live_first1)
    for k, v in sel_first1.items():
        merged_projection[k] += v

    summary = {
        "status": "ok",
        "raw_source": str(RAW_JSONL),
        "raw_count": len(raw_items),
        "selected_count": len(selected),
        "merged_first1_cap": merged_first1_cap,
        "selected_first1": dict(sel_first1),
        "selected_topics": dict(sel_topic),
        "selected_formats": dict(sel_format),
        "merged_projection_first1": dict(merged_projection),
        "rejected_by_cap_head": rejected_by_cap[:20],
        "paths": {
            "jsonl": str(OUT_JSONL),
            "tsv": str(OUT_TSV),
            "review_tsv": str(OUT_REVIEW_TSV),
        },
        "head": [
            {
                "scenario_id": x.get("scenario_id"),
                "topic": x.get("topic"),
                "format_type": x.get("format_type"),
                "opening_family": x.get("opening_family"),
                "text": x.get("text"),
            }
            for x in selected[:20]
        ]
    }

    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
