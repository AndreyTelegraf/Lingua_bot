from __future__ import annotations

import csv
import json
import unicodedata
from pathlib import Path

SHORTLIST = Path("data/sources/pilot_ptpt_001_shortlist.csv")
KAIKKI = Path("data/wiktionary/pt-extract.jsonl")
OUT = Path("data/sources/pilot_ptpt_001_enriched.csv")

ALLOWED_POS = {"noun", "verb", "adjective", "adverb"}

PT_HINTS = {
    "portugal",
    "português lusitano",
    "portugues lusitano",
}
BR_HINTS = {
    "brazil",
    "brasil",
    "brazilian",
}

def norm(s: str | None) -> str:
    if s is None:
        return ""
    return unicodedata.normalize("NFC", s).strip().lower()

def clean_ru_gloss(s: str | None) -> str:
    x = norm(s)
    if not x:
        return ""
    x = x.strip(" -–—;:,.")
    return x

def entry_score(obj: dict) -> int:
    score = 0

    categories = [norm(x) for x in obj.get("categories", []) if isinstance(x, str)]
    tags = [norm(x) for x in obj.get("tags", []) if isinstance(x, str)]

    sounds = obj.get("sounds", []) or []
    sound_tags = []
    for snd in sounds:
        if isinstance(snd, dict):
            for t in snd.get("tags", []) or []:
                if isinstance(t, str):
                    sound_tags.append(norm(t))

    blob = " | ".join(categories + tags + sound_tags)

    if any(h in blob for h in PT_HINTS):
        score += 20
    if any(h in blob for h in BR_HINTS):
        score -= 20

    translations = obj.get("translations", []) or []
    ru_count = sum(
        1
        for tr in translations
        if isinstance(tr, dict) and norm(tr.get("lang_code")) == "ru" and clean_ru_gloss(tr.get("word"))
    )
    score += ru_count * 5

    senses = obj.get("senses", []) or []
    score += min(len(senses), 5)

    return score

def extract_ru_translation(obj: dict) -> str:
    candidates: list[tuple[int, str]] = []

    for tr in obj.get("translations", []) or []:
        if not isinstance(tr, dict):
            continue
        if norm(tr.get("lang_code")) != "ru":
            continue
        word = clean_ru_gloss(tr.get("word"))
        if not word:
            continue

        # короче и проще — лучше
        word_count = len(word.split())
        length = len(word)
        penalty = 0

        if "," in word or ";" in word or "/" in word:
            penalty += 10
        if word_count > 3:
            penalty += 10

        candidates.append((penalty + word_count * 2 + length, word))

    if not candidates:
        return ""

    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][1]

def main() -> None:
    with SHORTLIST.open("r", encoding="utf-8", newline="") as f:
        shortlist_rows = list(csv.DictReader(f))

    shortlist_by_lemma = {norm(r["lemma"]): r for r in shortlist_rows}
    wanted = set(shortlist_by_lemma.keys())

    best: dict[str, dict] = {}

    with KAIKKI.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            obj = json.loads(line)

            if norm(obj.get("lang_code")) != "pt":
                continue

            lemma = norm(obj.get("word"))
            if lemma not in wanted:
                continue

            pos = norm(obj.get("pos"))
            if pos not in ALLOWED_POS:
                continue

            ru_gloss = extract_ru_translation(obj)
            if not ru_gloss:
                continue

            score = entry_score(obj)

            prev = best.get(lemma)
            if prev is None or score > prev["_score"]:
                best[lemma] = {
                    "_score": score,
                    "lemma": lemma,
                    "pos": pos,
                    "ru_gloss": ru_gloss,
                    "raw_obj": obj,
                }

    out_rows = []
    matched = 0

    for lemma in sorted(wanted):
        src = shortlist_by_lemma[lemma]
        hit = best.get(lemma)

        row = {
            "external_key": src["external_key"],
            "lemma": src["lemma"],
            "pos": hit["pos"] if hit else "",
            "level": src.get("level", "") or "",
            "freq_rank": src.get("freq_rank", "") or "",
            "ru_gloss": hit["ru_gloss"] if hit else "",
            "notes": "kaikki_pt_ru_enriched" if hit else "kaikki_no_match",
        }
        if hit:
            matched += 1
        out_rows.append(row)

    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["external_key", "lemma", "pos", "level", "freq_rank", "ru_gloss", "notes"],
        )
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"written={OUT}")
    print(f"shortlist_n={len(shortlist_rows)}")
    print(f"matched_n={matched}")
    print(f"unmatched_n={len(shortlist_rows) - matched}")

if __name__ == "__main__":
    main()
