from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
SCENARIO_PACK = ROOT / "data/community_authoring/scenario_pack_v2.json"
DB_AUDIT = ROOT / "data/community_quality/live_audit_after_micro_cut.json"
OUT_DIR = ROOT / "data/community_waves/wave_v5_raw"
SUMMARY_PATH = OUT_DIR / "community_replenishment_wave_v5_raw_summary.json"
JSONL_PATH = OUT_DIR / "community_replenishment_wave_v5_raw.jsonl"
TSV_PATH = OUT_DIR / "community_replenishment_wave_v5_raw.tsv"

OUT_DIR.mkdir(parents=True, exist_ok=True)

SPACE_RE = re.compile(r"\s+")
PUNCT_SPACE_RE = re.compile(r"\s+([,?.!])")
MULTI_Q_RE = re.compile(r"\?{2,}")
LEAD_TAIL_PUNCT_RE = re.compile(r"^[\s,.;:!?-]+|[\s,.;:!?-]+$")
BAD_STEMS_DEFAULT = {
    "как бы вы",
    "как по-португальски",
    "переведите",
    "буквально перевести",
    "официально сформулировать",
    "официально спросить",
    "чем в живой речи",
}

def norm(s: str) -> str:
    s = s.replace("ё", "е")
    s = s.replace("’", "'").replace("`", "'")
    s = s.replace("–", "-").replace("—", "-")
    s = SPACE_RE.sub(" ", s.strip())
    s = PUNCT_SPACE_RE.sub(r"\1", s)
    s = MULTI_Q_RE.sub("?", s)
    return s.strip()

def norm_key(s: str) -> str:
    s = norm(s).lower()
    s = re.sub(r"[\"'«»()]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ,.;:!?-")

def ensure_q(s: str) -> str:
    s = s.rstrip()
    if not s.endswith("?"):
        s = s.rstrip(" .!") + "?"
    return s

def ucfirst(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s

def trim_scene(scene: str) -> str:
    scene = norm(scene)
    scene = scene.rstrip(".")
    scene = re.sub(r"^\s*нужно\s+", "", scene, flags=re.I)
    scene = re.sub(r"^\s*если\s+", "", scene, flags=re.I)
    return scene

def trim_goal(goal: str) -> str:
    goal = norm(goal)
    goal = goal.rstrip(".")
    return goal

def trim_target(target: str) -> str:
    target = norm(target)
    target = target.rstrip(".")
    return target

def build_text(question_form: str, scene: str, goal: str, target: str) -> str:
    qf = norm(question_form).rstrip(" ,.;:")
    sc = trim_scene(scene)
    gl = trim_goal(goal)
    tg = trim_target(target)

    low = qf.lower()

    if low.endswith("если"):
        text = f"{qf} {sc.lower()}, чтобы это звучало {tg.lower()}?"
    elif low.endswith("когда"):
        text = f"{qf} {sc.lower()}, если хочется сказать это {tg.lower()}?"
    else:
        text = f"{qf} {sc.lower()}?"

    text = text.replace("если хочется сказать это по-человечески, чтобы это звучало", "чтобы это звучало")
    text = text.replace("если хочется сказать это ", "")
    text = text.replace("если хочется сказать это по-человечески", "по-человечески")
    text = text.replace("если хочется сказать это", "")
    text = text.replace("  ", " ")
    text = text.replace(" ,", ",")
    text = ucfirst(norm(text))
    text = ensure_q(text)
    return text

def first_tokens(text: str, n: int) -> str:
    toks = [t for t in re.split(r"\s+", norm_key(text)) if t]
    return " ".join(toks[:n])

def load_active_text_keys() -> set[str]:
    if not DB_AUDIT.exists():
        return set()
    data = json.loads(DB_AUDIT.read_text(encoding="utf-8"))
    rows = data.get("last_15_active", [])
    # audit file only contains tail rows, so do not rely on it for dedup of whole bank
    # keep empty set here; downstream constrained builder handles broader surface caps
    _ = rows
    return set()

def scenario_to_candidates(item: dict) -> list[dict]:
    scenario_id = item.get("scenario_id", "").strip()
    topic = (item.get("topic") or "").strip()
    fmt = (item.get("format_type") or "").strip()
    context = (item.get("context_label") or "").strip()
    scene = (item.get("scene") or "").strip()
    goal = (item.get("speaker_goal") or "").strip()
    natural_target = (item.get("natural_target") or "").strip()
    question_forms = item.get("question_forms") or []
    banned = {norm_key(x) for x in (item.get("banned_stems") or [])}
    banned |= {norm_key(x) for x in BAD_STEMS_DEFAULT}

    out = []
    for idx, qf in enumerate(question_forms, start=1):
        qf_norm = norm(qf)
        if not qf_norm:
            continue
        if any(norm_key(qf_norm).startswith(stem) for stem in banned if stem):
            continue

        text = build_text(qf_norm, scene, goal, natural_target)
        text_key = norm_key(text)
        if not text_key:
            continue
        if any(text_key.startswith(stem) for stem in banned if stem):
            continue

        out.append({
            "candidate_id": f"{scenario_id}__qf{idx}",
            "scenario_id": scenario_id,
            "topic": topic,
            "format_type": fmt,
            "opening_family": qf_norm,
            "context": context,
            "intent": goal,
            "natural_target": natural_target,
            "first1": first_tokens(text, 1),
            "first2": first_tokens(text, 2),
            "first3": first_tokens(text, 3),
            "text": text,
        })
    return out

def main() -> None:
    pack = json.loads(SCENARIO_PACK.read_text(encoding="utf-8"))
    if isinstance(pack, dict):
        scenarios = pack.get("items") or pack.get("scenarios") or []
    else:
        scenarios = pack

    active_text_keys = load_active_text_keys()

    raw = []
    seen_text = set()
    dropped = Counter()

    for item in scenarios:
        for cand in scenario_to_candidates(item):
            text_key = norm_key(cand["text"])
            sig = (cand["scenario_id"], cand["first3"], text_key)
            if text_key in active_text_keys:
                dropped["active_text_duplicate"] += 1
                continue
            if text_key in seen_text:
                dropped["raw_text_duplicate"] += 1
                continue
            if sig in seen_text:
                dropped["raw_signature_duplicate"] += 1
                continue
            seen_text.add(text_key)
            raw.append(cand)

    raw.sort(key=lambda x: (
        x["topic"],
        x["format_type"],
        x["first1"],
        x["first2"],
        x["scenario_id"],
        x["candidate_id"],
    ))

    with JSONL_PATH.open("w", encoding="utf-8") as f:
        for row in raw:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with TSV_PATH.open("w", encoding="utf-8") as f:
        f.write("candidate_id\tscenario_id\ttopic\tformat_type\topening_family\tcontext\tintent\tnatural_target\tfirst1\tfirst2\tfirst3\ttext\n")
        for row in raw:
            vals = [
                row["candidate_id"], row["scenario_id"], row["topic"], row["format_type"],
                row["opening_family"], row["context"], row["intent"], row["natural_target"],
                row["first1"], row["first2"], row["first3"], row["text"],
            ]
            f.write("\t".join(v.replace("\t", " ").replace("\n", " ") for v in vals) + "\n")

    summary = {
        "status": "ok",
        "scenario_count": len(scenarios),
        "raw_count": len(raw),
        "dropped": dict(dropped),
        "topics": dict(Counter(x["topic"] for x in raw)),
        "formats": dict(Counter(x["format_type"] for x in raw)),
        "first1": dict(Counter(x["first1"] for x in raw)),
        "first2": dict(Counter(x["first2"] for x in raw)),
        "first3": dict(Counter(x["first3"] for x in raw)),
        "paths": {
            "jsonl": str(JSONL_PATH),
            "tsv": str(TSV_PATH),
        },
        "head": raw[:12],
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
