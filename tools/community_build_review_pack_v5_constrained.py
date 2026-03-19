from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")

RAW_JSONL = ROOT / "data/community_waves/wave_v5_raw/community_replenishment_wave_v5_raw.jsonl"
OUT_JSONL = ROOT / "data/community_waves/wave_v5/community_replenishment_wave_v5_constrained.jsonl"
OUT_TSV = ROOT / "data/community_waves/wave_v5/community_replenishment_wave_v5_constrained.tsv"
REVIEW_TSV = ROOT / "data/community_review/review_pack_v5/community_review_pack_v5.tsv"
SUMMARY_JSON = ROOT / "data/community_review/review_pack_v5/community_review_pack_v5_summary.json"
LIVE_AUDIT = ROOT / "data/community_quality/live_audit_after_micro_cut.json"

OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
OUT_TSV.parent.mkdir(parents=True, exist_ok=True)
REVIEW_TSV.parent.mkdir(parents=True, exist_ok=True)

TARGET_NEW_ITEMS = 16
HARD_BLOCK_FIRST3 = {"что обычно говорят", "что обычно спрашивают"}
SOFT_BLOCK_FIRST2 = {"что обычно", "как мягко", "как здесь"}

def norm(s: str) -> str:
    s = (s or "").strip().lower().replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[,.!?;:]+$", "", s)
    return s

def sanitize_text(text: str) -> str:
    t = (text or "").strip()

    replacements = [
        (r"\bесли\s+уточнить,\s*", "если нужно уточнить, "),
        (r"\bесли\s+понять,\s*", "если нужно понять, "),
        (r"\bкогда\s+уточнить,\s*", "когда нужно уточнить, "),
        (r"\bкогда\s+понять,\s*", "когда нужно понять, "),
        (r"\bесли\s+попросить,\s*", "если нужно попросить, "),
        (r"\bкогда\s+попросить,\s*", "когда нужно попросить, "),
        (r"\bесли\s+быстро\s+переспросить,\s*", "если нужно быстро переспросить, "),
        (r"\bкогда\s+быстро\s+переспросить,\s*", "когда нужно быстро переспросить, "),
        (r"\bесли\s+быстро\s+и\s+нормально\s+спросить,\s*", "если нужно быстро и нормально спросить, "),
        (r"\bкогда\s+быстро\s+и\s+нормально\s+спросить,\s*", "когда нужно быстро и нормально спросить, "),
        (r"\bесли\s+без\s+неловкости\s+спросить,\s*", "если нужно без неловкости спросить, "),
        (r"\bкогда\s+без\s+неловкости\s+спросить,\s*", "когда нужно без неловкости спросить, "),
        (r"\bесли\s+спокойно\s+спросить,\s*", "если нужно спокойно спросить, "),
        (r"\bкогда\s+спокойно\s+спросить,\s*", "когда нужно спокойно спросить, "),
        (r"\bесли\s+заранее\s+обозначить,\s*", "если нужно заранее обозначить, "),
        (r"\bкогда\s+заранее\s+обозначить,\s*", "когда нужно заранее обозначить, "),
    ]

    for pattern, repl in replacements:
        t = re.sub(pattern, repl, t, flags=re.IGNORECASE)

    t = re.sub(r"\bШкола\b", "школа", t)
    t = re.sub(r"\bСрок\b", "срок", t)
    t = re.sub(r"\bКурьер\b", "курьер", t)
    t = re.sub(r"\bХозяин\b", "хозяин", t)
    t = re.sub(r"\bПосле\b", "после", t)
    t = re.sub(r"\bВыплыла\b", "выплыла", t)

    t = re.sub(r"\s+", " ", t).strip()
    return t

def first_tokens(text: str, n: int) -> str:
    toks = norm(text).split()
    return " ".join(toks[:n])

def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows

raw = load_jsonl(RAW_JSONL)
live_audit = json.loads(LIVE_AUDIT.read_text(encoding="utf-8"))
active_first1 = Counter(live_audit["first1"])
active_topics = Counter(live_audit["topics"])
active_formats = Counter(live_audit["formats"])

selected = []
seen_text = set()
reason_counts = Counter()
reason_examples = {}

for row in raw:
    text = sanitize_text((row.get("text") or "").strip())
    scenario_id = (row.get("scenario_id") or "").strip()
    topic = (row.get("topic") or "").strip()
    fmt = (row.get("format_type") or "").strip()
    opening = (row.get("opening_family") or "").strip()
    context = (row.get("context") or "").strip()
    intent = (row.get("intent") or "").strip()

    if not all([text, scenario_id, topic, fmt, opening, context, intent]):
        reason_counts["missing_required_field"] += 1
        continue

    f1 = first_tokens(row.get("first1") or text, 1)
    f2 = first_tokens(row.get("first2") or text, 2)
    f3 = first_tokens(row.get("first3") or text, 3)
    text_key = norm(text)

    if f3 in HARD_BLOCK_FIRST3:
        reason_counts["hard_block_first3"] += 1
        continue
    if f2 in SOFT_BLOCK_FIRST2:
        reason_counts["soft_block_first2"] += 1
        continue
    if text_key in seen_text:
        reason_counts["duplicate_text_in_raw"] += 1
        continue
    if active_first1[f1] + sum(1 for x in selected if x["first1"] == f1) >= 13:
        reason_counts["merged_first1_cap"] += 1
        reason_examples.setdefault("merged_first1_cap", [])
        if len(reason_examples["merged_first1_cap"]) < 5:
            reason_examples["merged_first1_cap"].append({
                "scenario_id": scenario_id,
                "text": text,
                "first1": f1,
            })
        continue

    selected.append({
        "scenario_id": scenario_id,
        "topic": topic,
        "format_type": fmt,
        "opening_family": opening,
        "context": context,
        "intent": intent,
        "review_action": "",
        "review_note": "",
        "text": text,
        "first1": f1,
    })
    seen_text.add(text_key)

topic_rank = {k: i for i, (k, _) in enumerate(sorted(active_topics.items(), key=lambda kv: (kv[1], kv[0])))}
format_rank = {k: i for i, (k, _) in enumerate(sorted(active_formats.items(), key=lambda kv: (kv[1], kv[0])))}

selected.sort(key=lambda r: (
    topic_rank.get(r["topic"], 999),
    format_rank.get(r["format_type"], 999),
    r["scenario_id"],
    r["text"],
))
selected = selected[:TARGET_NEW_ITEMS]

with OUT_JSONL.open("w", encoding="utf-8") as f:
    for row in selected:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

with OUT_TSV.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(["scenario_id", "opening_family", "context", "intent", "format_type", "topic", "text"])
    for r in selected:
        w.writerow([
            r["scenario_id"],
            r["opening_family"],
            r["context"],
            r["intent"],
            r["format_type"],
            r["topic"],
            r["text"],
        ])

with REVIEW_TSV.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(["scenario_id", "topic", "format_type", "opening_family", "context", "intent", "review_action", "review_note", "text"])
    for r in selected:
        w.writerow([
            r["scenario_id"],
            r["topic"],
            r["format_type"],
            r["opening_family"],
            r["context"],
            r["intent"],
            r["review_action"],
            r["review_note"],
            r["text"],
        ])

summary = {
    "status": "ok",
    "raw_source": str(RAW_JSONL),
    "active_count_before": sum(active_topics.values()),
    "candidate_count": len(raw),
    "selected_count": len(selected),
    "selected_topics": dict(Counter(r["topic"] for r in selected)),
    "selected_formats": dict(Counter(r["format_type"] for r in selected)),
    "selected_first1": dict(Counter(r["first1"] for r in selected)),
    "projected_first1_after_apply": {
        k: active_first1[k] + Counter(r["first1"] for r in selected)[k]
        for k in sorted(set(active_first1) | set(r["first1"] for r in selected))
    },
    "rejection_reason_counts": dict(reason_counts),
    "rejection_examples": reason_examples,
    "targets_v5": {
        "target_new_items": TARGET_NEW_ITEMS,
        "hard_block_first3": sorted(HARD_BLOCK_FIRST3),
        "soft_block_first2": sorted(SOFT_BLOCK_FIRST2),
    },
    "head": selected[:16],
}
SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
