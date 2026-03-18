from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

FORBID_PATTERNS: tuple[str, ...] = (
    "как бы вы",
    "чем в живой",
    "как по-португальски",
    "переведите на португальский",
    "буквально перевести",
    "официально спросить",
    "официально сформулировать",
    "дословно перевести",
)

FIRST_WORD_LIMIT_RATIO = 0.25
FIRST2_LIMIT_RATIO = 0.20
FIRST3_LIMIT_RATIO = 0.15

AWKWARD_STEMS: tuple[str, ...] = (
    "Как обычно называют на почте, чтобы",
    "Когда уместно сказать в Finanças, чтобы",
    "Что обычно говорят в школе ребёнка, чтобы проверить, правильно ли поняли",
    "О чём обычно уточняют при записи в Câmara, чтобы проверить, правильно ли поняли",
)

TEXT_TAILS: tuple[str, ...] = (
    "чтобы это звучало живо и по-местному?",
    "если хочется сказать естественно, а не как по учебнику?",
    "если нужен разговорный и нормальный вариант?",
    "чтобы не звучать слишком прямолинейно?",
)


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
    return text


def first_words(text: str, n: int) -> str:
    words = re.findall(r"[A-Za-zÀ-ÿА-Яа-яЁё0-9-]+", text.lower())
    return " ".join(words[:n])


def distribution_limit(target_size: int, ratio: float) -> int:
    return max(1, math.ceil(target_size * ratio))


def load_scenarios(path: Path) -> list[Scenario]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [Scenario.from_dict(row) for row in rows]


def render_text(scenario: Scenario, opening_family: str, seed_pick: int) -> str:
    variants = [
        f"{opening_family} {scenario.scene.lower()}",
        f"{opening_family} {scenario.scene.lower()}, если цель — {scenario.speaker_goal}",
        f"{opening_family} {scenario.scene.lower()}, чтобы фраза звучала естественно и по-живому",
    ]
    base = variants[seed_pick % len(variants)]
    tail = TEXT_TAILS[seed_pick % len(TEXT_TAILS)]
    return normalize(f"{base}, {tail}")


def would_break_prefix_limits(existing_texts: list[str], candidate_text: str, target_size: int) -> bool:
    first1_limit = distribution_limit(target_size, FIRST_WORD_LIMIT_RATIO)
    first2_limit = distribution_limit(target_size, FIRST2_LIMIT_RATIO)
    first3_limit = distribution_limit(target_size, FIRST3_LIMIT_RATIO)

    trial = existing_texts + [candidate_text]
    first1 = Counter(first_words(t, 1) for t in trial)
    first2 = Counter(first_words(t, 2) for t in trial)
    first3 = Counter(first_words(t, 3) for t in trial)

    return (
        max(first1.values()) > first1_limit
        or max(first2.values()) > first2_limit
        or max(first3.values()) > first3_limit
    )


def is_text_allowed(text: str, scenario: Scenario) -> bool:
    low = text.lower()

    if any(pat in low for pat in FORBID_PATTERNS):
        return False
    if any(pat.lower() in low for pat in scenario.banned_stems):
        return False
    if any(pat.lower() in low for pat in AWKWARD_STEMS):
        return False
    if not (85 <= len(text) <= 220):
        return False
    return True


def build_wave(
    target_size: int,
    max_per_opening: int,
    min_openings: int,
    seed: int,
    scenario_pack_path: Path,
) -> list[WaveItem]:
    random.seed(seed)

    scenarios = load_scenarios(scenario_pack_path)
    if not scenarios:
        raise ValueError("empty scenario pack")

    pool = scenarios[:]
    random.shuffle(pool)

    out: list[WaveItem] = []
    opening_counts: Counter[str] = Counter()
    used_scenarios: set[str] = set()

    scenario_cycle: list[Scenario] = []
    while len(scenario_cycle) < target_size * 8:
        block = pool[:]
        random.shuffle(block)
        scenario_cycle.extend(block)

    for scenario in scenario_cycle:
        if len(out) >= target_size:
            break
        if scenario.scenario_id in used_scenarios:
            continue

        forms = scenario.question_forms[:]
        random.shuffle(forms)

        built = False
        for idx, opening in enumerate(forms):
            if opening_counts[opening] >= max_per_opening:
                continue

            text = render_text(scenario, opening, seed_pick=seed + idx + len(out))
            if not is_text_allowed(text, scenario):
                continue
            if would_break_prefix_limits([item.text for item in out], text, target_size):
                continue

            out.append(
                WaveItem(
                    scenario_id=scenario.scenario_id,
                    opening_family=opening,
                    context=scenario.context_label,
                    intent=scenario.speaker_goal,
                    format_type=scenario.format_type,
                    topic=scenario.topic,
                    text=text,
                )
            )
            opening_counts[opening] += 1
            used_scenarios.add(scenario.scenario_id)
            built = True
            break

        if not built:
            continue

    unique_openings = len({item.opening_family for item in out})
    if unique_openings < min_openings:
        return []

    return out


def analyze(items: Iterable[WaveItem]) -> dict:
    items = list(items)
    texts = [i.text for i in items]

    first1 = Counter(first_words(t, 1) for t in texts)
    first2 = Counter(first_words(t, 2) for t in texts)
    first3 = Counter(first_words(t, 3) for t in texts)
    openings = Counter(i.opening_family for i in items)
    topics = Counter(i.topic for i in items)
    formats = Counter(i.format_type for i in items)
    scenario_ids = {i.scenario_id for i in items}
    lengths = [len(t) for t in texts]

    size = len(items)
    first1_limit = distribution_limit(size, FIRST_WORD_LIMIT_RATIO)
    first2_limit = distribution_limit(size, FIRST2_LIMIT_RATIO)
    first3_limit = distribution_limit(size, FIRST3_LIMIT_RATIO)

    violations: list[str] = []

    for k, v in first1.items():
        if v > first1_limit:
            violations.append(f"first1:{k}={v}>{first1_limit}")
    for k, v in first2.items():
        if v > first2_limit:
            violations.append(f"first2:{k}={v}>{first2_limit}")
    for k, v in first3.items():
        if v > first3_limit:
            violations.append(f"first3:{k}={v}>{first3_limit}")

    if not all(85 <= n <= 220 for n in lengths):
        violations.append("length_out_of_bounds")

    if len(scenario_ids) != len(items):
        violations.append("scenario_reuse_detected")

    awkward_hits = [text for text in texts if any(stem.lower() in text.lower() for stem in AWKWARD_STEMS)]
    if awkward_hits:
        violations.append("awkward_stem_detected")

    passed = not violations

    return {
        "generated_count": size,
        "passed": passed,
        "violations": violations,
        "unique_scenarios": len(scenario_ids),
        "openings": openings,
        "topics": topics,
        "formats": formats,
        "first1": first1,
        "first2": first2,
        "first3": first3,
        "length_min": min(lengths) if lengths else 0,
        "length_max": max(lengths) if lengths else 0,
        "length_avg": round(sum(lengths) / len(lengths), 2) if lengths else 0,
    }


def to_serializable_report(report: dict) -> dict:
    out = dict(report)
    for key in ("openings", "topics", "formats", "first1", "first2", "first3"):
        out[key] = dict(report[key])
    return out


def write_outputs(items: list[WaveItem], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "community_replenishment_wave_v2.jsonl"
    tsv_path = out_dir / "community_replenishment_wave_v2.tsv"

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
            f.write("\t".join(x.replace("\t", " ").replace("\n", " ") for x in row) + "\n")

    return jsonl_path, tsv_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-size", type=int, default=12)
    parser.add_argument("--max-per-opening", type=int, default=2)
    parser.add_argument("--min-openings", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--scenario-pack",
        type=Path,
        default=Path("data/community_authoring/scenario_pack_v1.json"),
    )
    parser.add_argument("--out-dir", type=Path, default=Path("data/community_waves/wave_v2"))
    args = parser.parse_args()

    items = build_wave(
        target_size=args.target_size,
        max_per_opening=args.max_per_opening,
        min_openings=args.min_openings,
        seed=args.seed,
        scenario_pack_path=args.scenario_pack,
    )
    report = analyze(items)

    payload = {
        "config": {
            "target_size": args.target_size,
            "max_per_opening": args.max_per_opening,
            "min_openings": args.min_openings,
            "seed": args.seed,
            "scenario_pack": str(args.scenario_pack),
            "out_dir": str(args.out_dir),
        },
        "report": to_serializable_report(report),
        "files": {},
    }

    if items:
        jsonl_path, tsv_path = write_outputs(items, args.out_dir)
        payload["files"] = {
            "jsonl": str(jsonl_path),
            "tsv": str(tsv_path),
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report["passed"] and len(items) == args.target_size else 2


if __name__ == "__main__":
    raise SystemExit(main())
