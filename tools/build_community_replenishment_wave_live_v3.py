from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

FORBID_PATTERNS = (
    "как бы вы",
    "как по-португальски",
    "чем в живой",
    "как в живой",
)

LIVE_FIRST1_LIMIT_RATIO = 0.45
LIVE_FIRST2_LIMIT_RATIO = 0.28
LIVE_FIRST3_LIMIT_RATIO = 0.18


@dataclass(slots=True)
class Scenario:
    scenario_id: str
    topic: str
    format_type: str
    context_label: str
    scene: str
    speaker_goal: str
    natural_target: str
    question_forms: list[str]
    banned_stems: list[str]

    @classmethod
    def from_dict(cls, row: dict) -> "Scenario":
        return cls(
            scenario_id=row["scenario_id"],
            topic=row["topic"],
            format_type=row["format_type"],
            context_label=row["context_label"],
            scene=row["scene"],
            speaker_goal=row["speaker_goal"],
            natural_target=row["natural_target"],
            question_forms=list(row["question_forms"]),
            banned_stems=list(row["banned_stems"]),
        )


@dataclass(slots=True)
class WaveItem:
    scenario_id: str
    opening_family: str
    context: str
    intent: str
    format_type: str
    topic: str
    text: str

    def as_json(self) -> dict:
        return asdict(self)


def normalize(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,?.!])", r"\1", text)
    text = text.replace(".,", ",")
    return text.strip()


def first_words(text: str, n: int) -> str:
    words = re.findall(r"[A-Za-zÀ-ÿА-Яа-яЁё0-9-]+", text.lower())
    return " ".join(words[:n])


def load_scenarios(path: Path) -> list[Scenario]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [Scenario.from_dict(row) for row in rows]


def load_live_texts(db_path: Path, table: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        f"SELECT text FROM {table} WHERE is_active = 1 ORDER BY id"
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]


def distribution_limit(total_size: int, ratio: float) -> int:
    return max(1, math.ceil(total_size * ratio))


def render_text(s: Scenario, opening: str, variant_idx: int) -> str:
    scene = s.scene.strip().rstrip(".!?")
    if scene:
        scene = scene[0].lower() + scene[1:]

    variants = [
        f"{opening} {scene}?",
        f"{opening} {scene}, если хочется сказать это по-человечески?",
        f"{opening} {scene}, чтобы это звучало естественно и без канцелярита?",
    ]
    return normalize(variants[variant_idx % len(variants)])


def text_allowed(text: str, scenario: Scenario) -> bool:
    low = text.lower()
    if any(p in low for p in FORBID_PATTERNS):
        return False
    if any(p.lower() in low for p in scenario.banned_stems):
        return False
    if not (85 <= len(text) <= 220):
        return False
    return True


def would_break_live_distribution(live_texts: list[str], new_texts: list[str], candidate: str) -> bool:
    all_texts = live_texts + new_texts + [candidate]
    total = len(all_texts)

    first1 = Counter(first_words(t, 1) for t in all_texts)
    first2 = Counter(first_words(t, 2) for t in all_texts)
    first3 = Counter(first_words(t, 3) for t in all_texts)

    if max(first1.values()) > distribution_limit(total, LIVE_FIRST1_LIMIT_RATIO):
        return True
    if max(first2.values()) > distribution_limit(total, LIVE_FIRST2_LIMIT_RATIO):
        return True
    if max(first3.values()) > distribution_limit(total, LIVE_FIRST3_LIMIT_RATIO):
        return True
    return False


def build_wave(
    db_path: Path,
    table: str,
    scenario_pack: Path,
    target_size: int,
    max_per_opening: int,
    min_openings: int,
    seed: int,
) -> list[WaveItem]:
    random.seed(seed)

    live_texts = load_live_texts(db_path, table)
    scenarios = load_scenarios(scenario_pack)
    random.shuffle(scenarios)

    out: list[WaveItem] = []
    opening_counts: Counter[str] = Counter()
    used_scenarios: set[str] = set()

    scenario_cycle: list[Scenario] = []
    while len(scenario_cycle) < target_size * 10:
        block = scenarios[:]
        random.shuffle(block)
        scenario_cycle.extend(block)

    for s in scenario_cycle:
        if len(out) >= target_size:
            break
        if s.scenario_id in used_scenarios:
            continue

        forms = s.question_forms[:]
        random.shuffle(forms)

        built = False
        for idx, opening in enumerate(forms):
            if opening_counts[opening] >= max_per_opening:
                continue

            candidate = render_text(s, opening, idx + len(out))
            if not text_allowed(candidate, s):
                continue
            if would_break_live_distribution(live_texts, [x.text for x in out], candidate):
                continue

            out.append(
                WaveItem(
                    scenario_id=s.scenario_id,
                    opening_family=opening,
                    context=s.context_label,
                    intent=s.speaker_goal,
                    format_type=s.format_type,
                    topic=s.topic,
                    text=candidate,
                )
            )
            opening_counts[opening] += 1
            used_scenarios.add(s.scenario_id)
            built = True
            break

        if not built:
            continue

    if len({x.opening_family for x in out}) < min_openings:
        return []

    return out


def analyze_wave(items: Iterable[WaveItem], live_texts: list[str]) -> dict:
    items = list(items)
    texts = [x.text for x in items]
    merged = live_texts + texts

    return {
        "generated_count": len(items),
        "unique_openings": len({x.opening_family for x in items}),
        "topics": dict(Counter(x.topic for x in items)),
        "formats": dict(Counter(x.format_type for x in items)),
        "wave_first1": dict(Counter(first_words(t, 1) for t in texts)),
        "wave_first2": dict(Counter(first_words(t, 2) for t in texts)),
        "wave_first3": dict(Counter(first_words(t, 3) for t in texts)),
        "merged_first1": dict(Counter(first_words(t, 1) for t in merged)),
        "merged_first2": dict(Counter(first_words(t, 2) for t in merged)),
        "merged_first3": dict(Counter(first_words(t, 3) for t in merged)),
        "length_min": min((len(t) for t in texts), default=0),
        "length_max": max((len(t) for t in texts), default=0),
        "length_avg": round(sum(len(t) for t in texts) / len(texts), 2) if texts else 0,
    }


def write_outputs(items: list[WaveItem], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "community_replenishment_wave_v3.jsonl"
    tsv_path = out_dir / "community_replenishment_wave_v3.tsv"

    with jsonl_path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item.as_json(), ensure_ascii=False) + "\n")

    with tsv_path.open("w", encoding="utf-8") as f:
        f.write("scenario_id\topening_family\tcontext\tintent\tformat_type\ttopic\ttext\n")
        for item in items:
            row = [
                item.scenario_id,
                item.opening_family,
                item.context,
                item.intent,
                item.format_type,
                item.topic,
                item.text,
            ]
            f.write("\t".join(str(x).replace("\t", " ").replace("\n", " ") for x in row) + "\n")

    return jsonl_path, tsv_path


def write_review_pack(items: list[WaveItem], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    tsv_path = out_dir / "community_review_pack_v2.tsv"
    with tsv_path.open("w", encoding="utf-8") as f:
        f.write("scenario_id\ttopic\tformat_type\topening_family\tcontext\tintent\treview_action\treview_note\ttext\n")
        for item in items:
            row = [
                item.scenario_id,
                item.topic,
                item.format_type,
                item.opening_family,
                item.context,
                item.intent,
                "keep",
                "",
                item.text,
            ]
            f.write("\t".join(str(x).replace("\t", " ").replace("\n", " ") for x in row) + "\n")
    return tsv_path


def write_import_preview(items: list[WaveItem], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "community_import_preview_v2.json"
    payload = {
        "accepted_count": len(items),
        "accepted": [
            {
                "topic": x.topic,
                "format_type": x.format_type,
                "text": x.text,
                "source_scenario_id": x.scenario_id,
                "opening_family": x.opening_family,
                "source_context": x.context,
                "source_intent": x.intent,
                "review_action": "keep",
                "review_note": "",
            }
            for x in items
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--table", default="community_content_items")
    parser.add_argument("--scenario-pack", type=Path, required=True)
    parser.add_argument("--target-size", type=int, default=12)
    parser.add_argument("--max-per-opening", type=int, default=2)
    parser.add_argument("--min-openings", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--review-out-dir", type=Path, required=True)
    parser.add_argument("--preview-out-dir", type=Path, required=True)
    args = parser.parse_args()

    live_texts = load_live_texts(args.db, args.table)
    items = build_wave(
        db_path=args.db,
        table=args.table,
        scenario_pack=args.scenario_pack,
        target_size=args.target_size,
        max_per_opening=args.max_per_opening,
        min_openings=args.min_openings,
        seed=args.seed,
    )
    report = analyze_wave(items, live_texts)
    files = {}

    if items:
        jsonl_path, tsv_path = write_outputs(items, args.out_dir)
        review_tsv = write_review_pack(items, args.review_out_dir)
        preview_json = write_import_preview(items, args.preview_out_dir)
        files = {
            "jsonl": str(jsonl_path),
            "tsv": str(tsv_path),
            "review_tsv": str(review_tsv),
            "preview_json": str(preview_json),
        }

    payload = {
        "config": {
            "db": str(args.db),
            "table": args.table,
            "scenario_pack": str(args.scenario_pack),
            "target_size": args.target_size,
            "max_per_opening": args.max_per_opening,
            "min_openings": args.min_openings,
            "seed": args.seed,
        },
        "report": report,
        "files": files,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if len(items) == args.target_size else 2


if __name__ == "__main__":
    raise SystemExit(main())
