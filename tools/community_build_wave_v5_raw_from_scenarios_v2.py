from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")

SCENARIO_PACK = ROOT / "data/community_authoring/scenario_pack_v2.json"
RAW_OUT_DIR = ROOT / "data/community_waves/wave_v5_raw"
RAW_JSONL = RAW_OUT_DIR / "community_replenishment_wave_v5_raw.jsonl"
RAW_TSV = RAW_OUT_DIR / "community_replenishment_wave_v5_raw.tsv"
RAW_SUMMARY = RAW_OUT_DIR / "community_replenishment_wave_v5_raw_summary.json"

RAW_OUT_DIR.mkdir(parents=True, exist_ok=True)

SPACE_RE = re.compile(r"\s+")
BAD_START_RE = re.compile(
    r"^(уточнить|понять|попросить|спросить|сказать|написать|объяснить|переспросить)\s+",
    flags=re.I,
)

HARD_BLOCK_FIRST3 = {
    "что обычно говорят",
    "что обычно спрашивают",
}
SOFT_BLOCK_FIRST2 = {
    "что обычно",
    "как мягко",
    "как здесь",
}

def norm(s: str) -> str:
    s = s or ""
    s = s.replace("ё", "е")
    s = s.replace("–", "-").replace("—", "-")
    s = s.replace("’", "'").replace("`", "'")
    s = SPACE_RE.sub(" ", s.strip())
    s = s.replace(" ,", ",").replace(" .", ".").replace(" ?", "?")
    return s.strip()

def norm_key(s: str) -> str:
    s = norm(s).lower()
    s = re.sub(r"[\"'«»()]", "", s)
    s = re.sub(r"[,.!?;:]+$", "", s)
    s = SPACE_RE.sub(" ", s)
    return s.strip()

def first_tokens(text: str, n: int) -> str:
    toks = norm_key(text).split()
    return " ".join(toks[:n])

def clean_scene(scene: str) -> str:
    s = norm(scene).rstrip(".")
    s = re.sub(r"^\s*нужно\s+", "", s, flags=re.I)
    return s

def clean_goal(goal: str) -> str:
    s = norm(goal).rstrip(".")
    s = BAD_START_RE.sub("", s)
    return s

def clean_target(target: str) -> str:
    return norm(target).rstrip(".").lower()

def sentence_case(s: str) -> str:
    s = norm(s)
    return s[:1].upper() + s[1:] if s else s

def ensure_q(s: str) -> str:
    s = s.rstrip()
    s = re.sub(r"[.!,;:]+$", "", s)
    return s + "?"

def build_text(question_form: str, scene: str, goal: str, target: str) -> str:
    qf = norm(question_form).rstrip(" ,.;:")
    scene = clean_scene(scene)
    goal = clean_goal(goal)
    target = clean_target(target)

    low = norm_key(qf)

    # "что обычно ..." формы
    if low.startswith("что обычно"):
        text = f"{qf} {scene}"
        if target:
            text += f", чтобы это звучало {target}"
        return ensure_q(sentence_case(text))

    # "о чем обычно ..." формы
    if low.startswith("о чем обычно"):
        text = f"{qf} {scene}"
        if target:
            text += f", чтобы это звучало {target}"
        return ensure_q(sentence_case(text))

    # "какими словами..." формы
    if low.startswith("какими словами"):
        text = f"{qf} {scene}"
        if target:
            text += f", чтобы это звучало {target}"
        return ensure_q(sentence_case(text))

    # "в какой форме...", "какой вариант...", "какой оборот..."
    if low.startswith("в какой форме") or low.startswith("какой вариант") or low.startswith("какой оборот"):
        text = f"{qf} {scene}"
        if target:
            text += f", чтобы это звучало {target}"
        return ensure_q(sentence_case(text))

    # "как в разговоре..."
    if low.startswith("как в разговоре"):
        text = f"{qf} {scene}"
        if target:
            text += f", чтобы это звучало {target}"
        return ensure_q(sentence_case(text))

    # "какая фраза..."
    if low.startswith("какая фраза"):
        text = f"{qf} {scene}"
        if target:
            text += f", чтобы это звучало {target}"
        return ensure_q(sentence_case(text))

    text = f"{qf} {scene}"
    if target:
        text += f", чтобы это звучало {target}"
    return ensure_q(sentence_case(text))

def scenario_items(pack: object) -> list[dict]:
    if isinstance(pack, list):
        return pack
    if isinstance(pack, dict):
        for key in ("items", "scenarios", "rows"):
            val = pack.get(key)
            if isinstance(val, list):
                return val
    return []

def main() -> None:
    pack = json.loads(SCENARIO_PACK.read_text(encoding="utf-8"))
    items = scenario_items(pack)

    raw: list[dict] = []
    seen_texts: set[str] = set()
    reason_counts = Counter()

    for item in items:
        scenario_id = norm(item.get("scenario_id", ""))
        topic = norm(item.get("topic", ""))
        fmt = norm(item.get("format_type", ""))
        context = norm(item.get("context_label", ""))
        scene = norm(item.get("scene", ""))
        goal = norm(item.get("speaker_goal", ""))
        target = norm(item.get("natural_target", ""))
        forms = item.get("question_forms") or []

        if not all([scenario_id, topic, fmt, context, scene, goal, target]) or not forms:
            reason_counts["missing_fields"] += 1
            continue

        for idx, qf in enumerate(forms, start=1):
            qf = norm(qf)
            if not qf:
                reason_counts["empty_question_form"] += 1
                continue

            text = build_text(qf, scene, goal, target)
            f1 = first_tokens(text, 1)
            f2 = first_tokens(text, 2)
            f3 = first_tokens(text, 3)

            if f3 in HARD_BLOCK_FIRST3:
                reason_counts["hard_block_first3"] += 1
                continue
            if f2 in SOFT_BLOCK_FIRST2:
                reason_counts["soft_block_first2"] += 1
                continue

            text_key = norm_key(text)
            if text_key in seen_texts:
                reason_counts["duplicate_text"] += 1
                continue
            seen_texts.add(text_key)

            raw.append({
                "candidate_id": f"{scenario_id}__qf{idx}",
                "scenario_id": scenario_id,
                "topic": topic,
                "format_type": fmt,
                "opening_family": qf,
                "context": context,
                "intent": goal,
                "natural_target": target,
                "first1": f1,
                "first2": f2,
                "first3": f3,
                "text": text,
            })

    raw.sort(key=lambda x: (
        x["topic"], x["format_type"], x["first1"], x["first2"], x["scenario_id"], x["candidate_id"]
    ))

    with RAW_JSONL.open("w", encoding="utf-8") as f:
        for row in raw:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with RAW_TSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow([
            "candidate_id", "scenario_id", "topic", "format_type", "opening_family",
            "context", "intent", "natural_target", "first1", "first2", "first3", "text"
        ])
        for row in raw:
            writer.writerow([
                row["candidate_id"], row["scenario_id"], row["topic"], row["format_type"],
                row["opening_family"], row["context"], row["intent"], row["natural_target"],
                row["first1"], row["first2"], row["first3"], row["text"]
            ])

    summary = {
        "status": "ok",
        "scenario_count": len(items),
        "raw_count": len(raw),
        "reason_counts": dict(reason_counts),
        "topics": dict(Counter(x["topic"] for x in raw)),
        "formats": dict(Counter(x["format_type"] for x in raw)),
        "first1": dict(Counter(x["first1"] for x in raw)),
        "first2": dict(Counter(x["first2"] for x in raw)),
        "first3": dict(Counter(x["first3"] for x in raw)),
        "paths": {
            "jsonl": str(RAW_JSONL),
            "tsv": str(RAW_TSV),
        },
        "head": raw[:15],
    }
    RAW_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
