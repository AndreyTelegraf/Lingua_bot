from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

SHORTLIST = Path("data/sources/pilot_ptpt_001_shortlist.csv")
KAIKKI = Path("data/wiktionary/pt-extract.jsonl")
OUT = Path("data/sources/pilot_ptpt_002_kaikki_pos.csv")

TARGET_POS = {"verb", "adjective", "adverb"}
CYR_RE = re.compile(r"[А-Яа-яЁё]")
BAD_RU_RE = re.compile(r"[;/]|[()]|\\[[^\\]]*\\]")
BAD_LEMMA_RE = re.compile(r"[0-9_]")

def norm(s: str) -> str:
    return " ".join((s or "").strip().split())

def load_shortlist() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    with SHORTLIST.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            lemma = norm(row.get("lemma", "")).lower()
            if not lemma:
                continue
            out[lemma] = {
                "external_key": norm(row.get("external_key", "")),
                "freq_rank": norm(row.get("freq_rank", "")),
                "level": norm(row.get("level", "")),
            }
    return out

def pick_ru_translation(obj: dict) -> str:
    candidates: list[str] = []
    for tr in obj.get("translations", []) or []:
        if not isinstance(tr, dict):
            continue
        if str(tr.get("lang_code") or "").strip() != "ru":
            continue
        word = norm(str(tr.get("word") or ""))
        if not word:
            continue
        if not CYR_RE.search(word):
            continue
        if BAD_RU_RE.search(word):
            continue
        if len(word.split()) > 2:
            continue
        candidates.append(word)

    if not candidates:
        return ""

    candidates.sort(key=lambda x: (len(x.split()), len(x)))
    return candidates[0]

def main() -> None:
    shortlist = load_shortlist()
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    stats = Counter()

    with KAIKKI.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except Exception:
                stats["json_error"] += 1
                continue

            if str(obj.get("lang_code") or "") != "pt":
                continue

            lemma = norm(str(obj.get("word") or "")).lower()
            pos = norm(str(obj.get("pos") or "")).lower()

            if not lemma or not pos:
                continue
            if pos not in TARGET_POS:
                continue
            if lemma not in shortlist:
                continue
            if BAD_LEMMA_RE.search(lemma):
                stats["bad_lemma_shape"] += 1
                continue

            key = (lemma, pos)
            if key in seen:
                stats["duplicate_lemma_pos"] += 1
                continue

            ru = pick_ru_translation(obj)
            if not ru:
                stats["missing_ru_translation"] += 1
                continue

            seen.add(key)
            meta = shortlist[lemma]
            rows.append(
                {
                    "external_key": meta["external_key"] or f"kaikki:{lemma}:{pos}",
                    "lemma": lemma,
                    "pos": pos,
                    "level": meta["level"],
                    "freq_rank": meta["freq_rank"],
                    "ru_gloss": ru,
                    "notes": "kaikki_pt_ru_pos_seed",
                }
            )
            stats[f"kept_{pos}"] += 1

    rows.sort(key=lambda r: ({"verb": 1, "adjective": 2, "adverb": 3}.get(r["pos"], 99), int(r["freq_rank"] or "999999"), r["lemma"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["external_key", "lemma", "pos", "level", "freq_rank", "ru_gloss", "notes"],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"written={OUT}")
    print(f"rows={len(rows)}")
    print("stats:")
    for k in sorted(stats):
        print(f"{k}={stats[k]}")

if __name__ == "__main__":
    main()
