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

OPENING_FAMILIES: list[str] = [
    "Что обычно говорят",
    "Как обычно называют",
    "Какая фраза здесь звучит",
    "Где чаще спотыкаются в речи",
    "Когда уместно сказать",
    "Зачем здесь добавляют",
    "Почему местные скорее скажут",
    "В какой форме лучше спросить",
    "О чём обычно уточняют",
    "Какими словами мягче сказать",
    "Какой оборот здесь звучит естественно",
    "В каком варианте это звучит живее",
]

CONTEXTS: list[str] = [
    "при аренде квартиры",
    "в переписке с senhorio",
    "в разговоре с врачом",
    "в супермаркете",
    "в кафе",
    "на почте",
    "в Finanças",
    "в AIMA",
    "в школе ребёнка",
    "в чате соседей",
    "в сервисе доставки",
    "в разговоре с механиком",
    "на автовокзале",
    "в клинике",
    "при записи в Câmara",
]

CONTEXT_TO_INTENTS: dict[str, list[str]] = {
    "при аренде квартиры": [
        "чтобы вежливо уточнить цену",
        "чтобы спросить, какие документы нужны",
        "чтобы мягко обозначить проблему",
        "чтобы уточнить, можно ли перенести встречу",
        "чтобы договориться о времени",
        "чтобы спросить о сроках",
        "чтобы выяснить, что делать дальше",
    ],
    "в переписке с senhorio": [
        "чтобы вежливо уточнить цену",
        "чтобы мягко обозначить проблему",
        "чтобы уточнить, можно ли перенести встречу",
        "чтобы договориться о времени",
        "чтобы аккуратно отказаться",
        "чтобы спросить о сроках",
        "чтобы выяснить, что делать дальше",
    ],
    "в разговоре с врачом": [
        "чтобы мягко обозначить проблему",
        "чтобы переспросить без грубости",
        "чтобы попросить ответ попроще",
        "чтобы проверить, правильно ли поняли",
        "чтобы спросить о сроках",
        "чтобы выяснить, что делать дальше",
    ],
    "в супермаркете": [
        "чтобы вежливо уточнить цену",
        "чтобы переспросить без грубости",
        "чтобы уточнить, что входит в услугу",
        "чтобы аккуратно отказаться",
        "чтобы проверить, правильно ли поняли",
    ],
    "в кафе": [
        "чтобы вежливо уточнить цену",
        "чтобы переспросить без грубости",
        "чтобы уточнить, что входит в услугу",
        "чтобы аккуратно отказаться",
        "чтобы проверить, правильно ли поняли",
    ],
    "на почте": [
        "чтобы спросить, какие документы нужны",
        "чтобы переспросить без грубости",
        "чтобы договориться о времени",
        "чтобы проверить, правильно ли поняли",
        "чтобы спросить о сроках",
        "чтобы выяснить, что делать дальше",
    ],
    "в Finanças": [
        "чтобы спросить, какие документы нужны",
        "чтобы переспросить без грубости",
        "чтобы попросить ответ попроще",
        "чтобы проверить, правильно ли поняли",
        "чтобы спросить о сроках",
        "чтобы выяснить, что делать дальше",
    ],
    "в AIMA": [
        "чтобы спросить, какие документы нужны",
        "чтобы переспросить без грубости",
        "чтобы попросить ответ попроще",
        "чтобы проверить, правильно ли поняли",
        "чтобы спросить о сроках",
        "чтобы выяснить, что делать дальше",
    ],
    "в школе ребёнка": [
        "чтобы уточнить, можно ли перенести встречу",
        "чтобы переспросить без грубости",
        "чтобы договориться о времени",
        "чтобы проверить, правильно ли поняли",
        "чтобы спросить о сроках",
    ],
    "в чате соседей": [
        "чтобы мягко обозначить проблему",
        "чтобы уточнить, можно ли перенести встречу",
        "чтобы переспросить без грубости",
        "чтобы договориться о времени",
        "чтобы аккуратно отказаться",
        "чтобы проверить, правильно ли поняли",
    ],
    "в сервисе доставки": [
        "чтобы вежливо уточнить цену",
        "чтобы мягко обозначить проблему",
        "чтобы переспросить без грубости",
        "чтобы попросить ответ попроще",
        "чтобы проверить, правильно ли поняли",
        "чтобы спросить о сроках",
    ],
    "в разговоре с механиком": [
        "чтобы вежливо уточнить цену",
        "чтобы мягко обозначить проблему",
        "чтобы переспросить без грубости",
        "чтобы уточнить, что входит в услугу",
        "чтобы проверить, правильно ли поняли",
        "чтобы спросить о сроках",
    ],
    "на автовокзале": [
        "чтобы переспросить без грубости",
        "чтобы договориться о времени",
        "чтобы попросить ответ попроще",
        "чтобы проверить, правильно ли поняли",
        "чтобы спросить о сроках",
        "чтобы выяснить, что делать дальше",
    ],
    "в клинике": [
        "чтобы мягко обозначить проблему",
        "чтобы переспросить без грубости",
        "чтобы попросить ответ попроще",
        "чтобы проверить, правильно ли поняли",
        "чтобы спросить о сроках",
        "чтобы выяснить, что делать дальше",
    ],
    "при записи в Câmara": [
        "чтобы спросить, какие документы нужны",
        "чтобы уточнить, можно ли перенести встречу",
        "чтобы переспросить без грубости",
        "чтобы договориться о времени",
        "чтобы проверить, правильно ли поняли",
        "чтобы спросить о сроках",
        "чтобы выяснить, что делать дальше",
    ],
}

FORBID_PATTERNS: tuple[str, ...] = (
    "как бы вы",
    "чем в живой",
    "как по-португальски",
)

FIRST_WORD_LIMIT_RATIO = 0.25
FIRST2_LIMIT_RATIO = 0.20
FIRST3_LIMIT_RATIO = 0.15


@dataclass(slots=True)
class WaveItem:
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


def pick_topics() -> list[str]:
    return [
        "housing",
        "documents",
        "shopping",
        "work",
        "transport",
        "services",
        "financas",
        "culture",
        "bureaucracy",
        "health",
        "food",
    ]


def pick_formats() -> list[str]:
    return ["dialogue", "local", "nuance"]


def is_semantically_valid(context: str, intent: str) -> bool:
    allowed = CONTEXT_TO_INTENTS.get(context, [])
    return intent in allowed


def render_text(opening: str, context: str, intent: str) -> str:
    templates = [
        f"{opening} {context}, {intent}, чтобы это звучало живо и по-местному?",
        f"{opening} {context}, {intent}, если хочется сказать естественно, а не как по учебнику?",
        f"{opening} {context}, {intent}, если нужен разговорный и нормальный вариант?",
        f"{opening} {context}, {intent}, чтобы не звучать слишком прямолинейно?",
    ]
    text = random.choice(templates)
    return normalize(text)


def distribution_limit(target_size: int, ratio: float) -> int:
    return max(1, math.ceil(target_size * ratio))


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


def build_wave(target_size: int, max_per_family: int, min_families: int, seed: int) -> list[WaveItem]:
    random.seed(seed)

    if min_families > len(OPENING_FAMILIES):
        raise ValueError("min_families exceeds opening families count")

    selected_families = OPENING_FAMILIES[:]
    random.shuffle(selected_families)
    selected_families = selected_families[:max(min_families, min(target_size, len(OPENING_FAMILIES)))]

    contexts = CONTEXTS[:]
    topics = pick_topics()
    formats = pick_formats()

    random.shuffle(contexts)
    random.shuffle(topics)
    random.shuffle(formats)

    out: list[WaveItem] = []
    family_counts: Counter[str] = Counter()

    topic_idx = 0
    format_idx = 0

    family_cycle: list[str] = []
    while len(family_cycle) < target_size * 10:
        block = selected_families[:]
        random.shuffle(block)
        family_cycle.extend(block)

    context_cycle: list[str] = []
    while len(context_cycle) < target_size * 10:
        block = contexts[:]
        random.shuffle(block)
        context_cycle.extend(block)

    ctx_ptr = 0

    for family in family_cycle:
        if len(out) >= target_size:
            break
        if family_counts[family] >= max_per_family:
            continue

        built = False
        for _ in range(len(context_cycle)):
            context = context_cycle[ctx_ptr % len(context_cycle)]
            ctx_ptr += 1

            allowed_intents = CONTEXT_TO_INTENTS[context][:]
            random.shuffle(allowed_intents)

            for intent in allowed_intents:
                topic = topics[topic_idx % len(topics)]
                format_type = formats[format_idx % len(formats)]
                topic_idx += 1
                format_idx += 1

                text = render_text(family, context, intent)
                low = text.lower()

                if any(pat in low for pat in FORBID_PATTERNS):
                    continue
                if not (70 <= len(text) <= 160):
                    continue
                if not is_semantically_valid(context, intent):
                    continue
                if would_break_prefix_limits([item.text for item in out], text, target_size):
                    continue

                out.append(
                    WaveItem(
                        opening_family=family,
                        context=context,
                        intent=intent,
                        format_type=format_type,
                        topic=topic,
                        text=text,
                    )
                )
                family_counts[family] += 1
                built = True
                break

            if built:
                break

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

    if not all(70 <= n <= 160 for n in lengths):
        violations.append("length_out_of_bounds")

    semantic_invalid = [
        {"context": i.context, "intent": i.intent, "text": i.text}
        for i in items
        if not is_semantically_valid(i.context, i.intent)
    ]
    if semantic_invalid:
        violations.append("semantic_invalid_pairs")

    passed = not violations

    return {
        "generated_count": size,
        "passed": passed,
        "violations": violations,
        "semantic_invalid_count": len(semantic_invalid),
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
    jsonl_path = out_dir / "community_replenishment_wave_v1.jsonl"
    tsv_path = out_dir / "community_replenishment_wave_v1.tsv"

    with jsonl_path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item.as_json(), ensure_ascii=False) + "\n")

    with tsv_path.open("w", encoding="utf-8") as f:
        f.write("opening_family\tcontext\tintent\tformat_type\ttopic\ttext\n")
        for item in items:
            row = [
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
    parser.add_argument("--target-size", type=int, default=16)
    parser.add_argument("--max-per-family", type=int, default=2)
    parser.add_argument("--min-families", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", type=Path, default=Path("data/community_waves/wave_v1"))
    args = parser.parse_args()

    items = build_wave(
        target_size=args.target_size,
        max_per_family=args.max_per_family,
        min_families=args.min_families,
        seed=args.seed,
    )
    report = analyze(items)

    payload = {
        "config": {
            "target_size": args.target_size,
            "max_per_family": args.max_per_family,
            "min_families": args.min_families,
            "seed": args.seed,
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
