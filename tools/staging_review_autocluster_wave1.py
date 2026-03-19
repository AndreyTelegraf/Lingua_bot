from __future__ import annotations
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
IN_DIR = ROOT / "data/master_source_v1/processed/staging_full_diagnostics_pack_v2"
IN_CSV = IN_DIR / "active_bank_review.csv"
OUT_DIR = ROOT / "data/master_source_v1/processed/staging_review_autocluster_wave1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

if not IN_CSV.exists():
    raise SystemExit(f"Missing input CSV: {IN_CSV}")

def norm(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).strip()

def tokenize(s: str) -> list[str]:
    return re.findall(r"[a-zA-Zа-яА-Я0-9_+\-]+", s.lower())

def detect_source_family(row: dict) -> str:
    joined = " | ".join(norm(v) for v in row.values()).lower()
    for fam in ("pilot_safe", "enriched_qc", "kaikki", "safe_promote", "openwordnet"):
        if fam in joined:
            return fam
    return "unknown"

def detect_primary_flag(row: dict) -> str:
    joined = " | ".join(norm(v) for v in row.values()).lower()
    candidates = [
        "length_outlier_in_choices",
        "correct_not_in_choices",
        "proper_name_like",
        "transparent_pair",
        "legacy_source_family",
    ]
    hits = [c for c in candidates if c in joined]
    if hits:
        for c in candidates:
            if c in hits:
                return c
    return "unknown"

def choose_col(fieldnames: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in fieldnames:
            return c
    return None

with IN_CSV.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fieldnames = reader.fieldnames or []

if not rows:
    raise SystemExit("active_bank_review.csv is empty")

id_col = choose_col(fieldnames, ["item_id", "id"])
lemma_col = choose_col(fieldnames, ["lemma"])
correct_col = choose_col(fieldnames, ["correct_answer"])
pos_col = choose_col(fieldnames, ["pos"])
topic_col = choose_col(fieldnames, ["topic_tag"])
bin_col = choose_col(fieldnames, ["bin_name"])
freq_col = choose_col(fieldnames, ["freq_rank"])
review_reason_col = choose_col(fieldnames, ["review_reason", "reason", "flag", "flags"])
choices_col = choose_col(fieldnames, ["choices", "choices_json", "option_texts_json"])
source_col = choose_col(fieldnames, ["source_family", "source", "import_source", "provenance"])

enriched_rows: list[dict] = []
for row in rows:
    source_family = norm(row.get(source_col)) or detect_source_family(row)
    primary_flag = norm(row.get(review_reason_col)) or detect_primary_flag(row)
    lemma = norm(row.get(lemma_col))
    correct = norm(row.get(correct_col))
    pos = norm(row.get(pos_col))
    topic = norm(row.get(topic_col))
    bin_name = norm(row.get(bin_col))
    freq_rank_raw = norm(row.get(freq_col))
    try:
        freq_rank = int(freq_rank_raw) if freq_rank_raw else None
    except Exception:
        freq_rank = None

    text_surface = " | ".join(norm(v) for v in row.values())
    tokens = tokenize(text_surface)

    human_cluster = None
    if primary_flag == "correct_not_in_choices":
        human_cluster = "deactivate_now_correct_missing"
    elif primary_flag == "proper_name_like":
        human_cluster = "deactivate_now_proper_name"
    elif primary_flag == "transparent_pair":
        human_cluster = "review_transparent_pair"
    elif primary_flag == "length_outlier_in_choices":
        if len(correct) <= 4:
            human_cluster = "review_length_outlier_short_correct"
        elif len(correct) >= 12:
            human_cluster = "review_length_outlier_long_correct"
        else:
            human_cluster = "review_length_outlier_generic"
    elif primary_flag == "legacy_source_family":
        if source_family in {"pilot_safe", "enriched_qc", "kaikki"}:
            human_cluster = f"review_legacy_{source_family}"
        else:
            human_cluster = "review_legacy_other"
    else:
        human_cluster = "review_uncategorized"

    severity = "review"
    action = "manual_review"
    if human_cluster.startswith("deactivate_now_"):
        severity = "deactivate_now"
        action = "deactivate"
    elif human_cluster.startswith("review_length_outlier_"):
        severity = "review_high"
        action = "repair_or_deactivate"
    elif human_cluster.startswith("review_transparent_pair"):
        severity = "review_high"
        action = "repair_or_deactivate"
    elif human_cluster.startswith("review_legacy_"):
        severity = "review_medium"
        action = "repair_pack_first"

    enriched = {
        "item_pk": norm(row.get(id_col)) if id_col else "",
        "lemma": lemma,
        "correct_answer": correct,
        "pos": pos,
        "topic_tag": topic,
        "bin_name": bin_name,
        "freq_rank": freq_rank,
        "source_family": source_family,
        "primary_flag": primary_flag,
        "human_cluster": human_cluster,
        "severity": severity,
        "suggested_action": action,
        "raw_row": row,
        "text_surface": text_surface,
        "token_sample": tokens[:20],
    }
    enriched_rows.append(enriched)

cluster_counts = Counter(r["human_cluster"] for r in enriched_rows)
flag_counts = Counter(r["primary_flag"] for r in enriched_rows)
source_counts = Counter(r["source_family"] for r in enriched_rows)
pos_counts = Counter(r["pos"] or "unknown" for r in enriched_rows)
severity_counts = Counter(r["severity"] for r in enriched_rows)

by_cluster: dict[str, list[dict]] = defaultdict(list)
for r in enriched_rows:
    by_cluster[r["human_cluster"]].append(r)

def sort_key(r: dict):
    freq_rank = r["freq_rank"]
    return (
        10**9 if freq_rank is None else freq_rank,
        r["lemma"],
        r["item_pk"],
    )

top_examples = {}
for cluster, items in sorted(by_cluster.items()):
    top_examples[cluster] = [
        {
            "item_pk": x["item_pk"],
            "lemma": x["lemma"],
            "correct_answer": x["correct_answer"],
            "pos": x["pos"],
            "topic_tag": x["topic_tag"],
            "bin_name": x["bin_name"],
            "freq_rank": x["freq_rank"],
            "source_family": x["source_family"],
            "primary_flag": x["primary_flag"],
            "suggested_action": x["suggested_action"],
        }
        for x in sorted(items, key=sort_key)[:20]
    ]

deactivate_now = [r for r in enriched_rows if r["severity"] == "deactivate_now"]
review_high = [r for r in enriched_rows if r["severity"] == "review_high"]
review_medium = [r for r in enriched_rows if r["severity"] == "review_medium"]
uncategorized = [r for r in enriched_rows if r["human_cluster"] == "review_uncategorized"]

summary = {
    "input_csv": str(IN_CSV),
    "rows_total": len(enriched_rows),
    "cluster_counts": dict(cluster_counts.most_common()),
    "flag_counts": dict(flag_counts.most_common()),
    "source_family_counts": dict(source_counts.most_common()),
    "pos_counts": dict(pos_counts.most_common()),
    "severity_counts": dict(severity_counts.most_common()),
    "deactivate_now_count": len(deactivate_now),
    "review_high_count": len(review_high),
    "review_medium_count": len(review_medium),
    "uncategorized_count": len(uncategorized),
    "utc_timestamp": datetime.now(UTC).isoformat(),
}

(OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT_DIR / "top_examples_by_cluster.json").write_text(json.dumps(top_examples, ensure_ascii=False, indent=2), encoding="utf-8")

def write_csv(path: Path, items: list[dict]) -> None:
    cols = [
        "item_pk", "lemma", "correct_answer", "pos", "topic_tag", "bin_name",
        "freq_rank", "source_family", "primary_flag", "human_cluster",
        "severity", "suggested_action"
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(items, key=sort_key):
            w.writerow({k: r.get(k) for k in cols})

write_csv(OUT_DIR / "review_autocluster_full.csv", enriched_rows)
write_csv(OUT_DIR / "review_autocluster_deactivate_now.csv", deactivate_now)
write_csv(OUT_DIR / "review_autocluster_high.csv", review_high)
write_csv(OUT_DIR / "review_autocluster_medium.csv", review_medium)
write_csv(OUT_DIR / "review_autocluster_uncategorized.csv", uncategorized)

wave_plan = {
    "wave_1_immediate": {
        "goal": "finish any remaining hard-deactivate items before broader repair",
        "input": "review_autocluster_deactivate_now.csv",
        "count": len(deactivate_now),
    },
    "wave_2_high": {
        "goal": "repair or deactivate high-embarrassment distractor packs first",
        "input": "review_autocluster_high.csv",
        "count": len(review_high),
        "priority_clusters": [
            c for c, _ in cluster_counts.most_common()
            if c.startswith("review_length_outlier_") or c == "review_transparent_pair"
        ],
    },
    "wave_3_medium": {
        "goal": "legacy cleanup by source family",
        "input": "review_autocluster_medium.csv",
        "count": len(review_medium),
        "priority_clusters": [
            c for c, _ in cluster_counts.most_common()
            if c.startswith("review_legacy_")
        ],
    },
    "wave_4_tail": {
        "goal": "inspect uncategorized tail and extend heuristics",
        "input": "review_autocluster_uncategorized.csv",
        "count": len(uncategorized),
    },
}
(OUT_DIR / "wave_plan.json").write_text(json.dumps(wave_plan, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(summary, ensure_ascii=False, indent=2))
print("\nTOP_CLUSTERS")
for k, v in cluster_counts.most_common(20):
    print(f"{k}: {v}")
