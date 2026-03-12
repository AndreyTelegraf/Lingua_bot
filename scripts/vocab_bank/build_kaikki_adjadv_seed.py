from __future__ import annotations

import csv
import json
from pathlib import Path

SHORTLIST_CSV = Path("data/sources/pilot_ptpt_001_shortlist.csv")
KAIKKI_JSONL = Path("data/wiktionary/pt-extract.jsonl")
OUT_CSV = Path("data/sources/pilot_ptpt_003_kaikki_adjadv.csv")


def load_shortlist_freq() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    with SHORTLIST_CSV.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            lemma = (row.get("lemma") or "").strip().lower()
            freq_rank = (row.get("freq_rank") or "").strip()
            external_key = (row.get("external_key") or "").strip()
            if lemma:
                out[lemma] = (external_key, freq_rank)
    return out


def pick_ru_translation(obj: dict) -> str | None:
    translations = obj.get("translations") or []
    if not isinstance(translations, list):
        return None

    for tr in translations:
        if not isinstance(tr, dict):
            continue
        if (tr.get("lang_code") or "") != "ru":
            continue
        word = (tr.get("word") or "").strip()
        if not word:
            continue
        bad = False
        for ch in (";", "/", "(", ")", "[", "]", ","):
            if ch in word:
                bad = True
                break
        if bad:
            continue
        if " " in word:
            continue
        return word
    return None


def main() -> None:
    shortlist = load_shortlist_freq()
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, str]] = []

    stats = {
        "kept_adjective": 0,
        "kept_adverb": 0,
        "blocked_adverb_mente": 0,
        "missing_ru_translation": 0,
        "duplicate_lemma_pos": 0,
        "non_pt": 0,
        "non_target_pos": 0,
        "not_in_shortlist": 0,
    }

    with KAIKKI_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)

            if obj.get("lang_code") != "pt":
                stats["non_pt"] += 1
                continue

            raw_pos = (obj.get("pos") or "").strip().lower()
            if raw_pos == "adj":
                pos = "adjective"
            elif raw_pos == "adv":
                pos = "adverb"
            else:
                stats["non_target_pos"] += 1
                continue

            lemma = (obj.get("word") or "").strip().lower()
            if not lemma:
                continue

            if lemma not in shortlist:
                stats["not_in_shortlist"] += 1
                continue

            ru = pick_ru_translation(obj)
            if not ru:
                stats["missing_ru_translation"] += 1
                continue

            if pos == "adverb" and lemma.endswith("mente"):
                stats["blocked_adverb_mente"] += 1
                continue

            key = (lemma, pos)
            if key in seen:
                stats["duplicate_lemma_pos"] += 1
                continue
            seen.add(key)

            external_key, freq_rank = shortlist[lemma]

            if pos == "adjective":
                stats["kept_adjective"] += 1
            else:
                stats["kept_adverb"] += 1

            rows.append(
                {
                    "external_key": f"kaikki-{pos}-{lemma}",
                    "lemma": lemma,
                    "pos": pos,
                    "level": "",
                    "freq_rank": freq_rank,
                    "ru_gloss": ru,
                    "notes": "kaikki_pt_ru_adjadv_seed",
                }
            )

    rows.sort(key=lambda r: (r["pos"], int(r["freq_rank"]), r["lemma"]))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["external_key", "lemma", "pos", "level", "freq_rank", "ru_gloss", "notes"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"written={OUT_CSV}")
    print(f"rows={len(rows)}")
    print("stats:")
    for k, v in stats.items():
        print(f"{k}={v}")


if __name__ == "__main__":
    main()
