from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

SRC = Path("data/sources/pilot_ptpt_001_enriched_qc.csv")
OUT = Path("data/sources/pilot_ptpt_001_pilot_safe.csv")

MAX_ROWS = 800
ALLOWED_POS = {"noun", "verb"}

BAD_LEMMA_EXACT = {
    "abel", "adão", "afonso", "josé", "paulo",
    "abril", "maio", "junho", "julho", "agosto",
    "setembro", "outubro", "novembro", "dezembro", "março", "janeiro",
    "portugal", "américa", "brasil", "angola", "moçambique",
    "merda",
}

BAD_LEMMA_SUBSTR = {
    "cristo", "jesus", "deus", "igrej", "santo", "santa",
    "padre", "bispo", "freira", "mosteir", "catedral",
}

BAD_GLOSS_EXACT = {
    "говно",
    "иосиф",
    "адам",
    "авель",
    "обряд",
    "иск",
    "надёжность",
    "плоскость",
    "случай",
    "состав",
    "штат",
    "мент",
    "фес",
}

BAD_PAIRS = {
    ("segundo", "второй"),
    ("processo", "иск"),
    ("certeza", "надёжность"),
    ("evento", "случай"),
    ("serviço", "обряд"),
    ("plano", "плоскость"),
    ("equipe", "состав"),
    ("pessoal", "штат"),
    ("tempo", "час"),
    ("bem", "благо"),
    ("mal", "зло"),
    ("pena", "перо"),
    ("acordo", "сделка"),
    ("educação", "воспитание"),
    ("justiça", "право"),
    ("pensar", "найти"),
    ("falar", "сказать"),
    ("achar", "думать"),
}

def norm(s: str | None) -> str:
    if s is None:
        return ""
    return unicodedata.normalize("NFC", s).strip().lower()

def parse_rank(s: str | None) -> int:
    x = norm(s)
    if not x:
        return 999999999
    try:
        return int(float(x))
    except Exception:
        return 999999999

def keep(row: dict[str, str]) -> tuple[bool, str | None]:
    lemma = norm(row.get("lemma"))
    pos = norm(row.get("pos"))
    gloss = norm(row.get("ru_gloss"))

    if pos not in ALLOWED_POS:
        return False, "bad_pos"
    if not gloss:
        return False, "missing_gloss"
    if lemma in BAD_LEMMA_EXACT:
        return False, "bad_lemma_exact"
    if any(x in lemma for x in BAD_LEMMA_SUBSTR):
        return False, "bad_lemma_substr"
    if gloss in BAD_GLOSS_EXACT:
        return False, "bad_gloss_exact"
    if (lemma, gloss) in BAD_PAIRS:
        return False, "bad_pair"
    if len(lemma) < 3:
        return False, "lemma_too_short"
    if len(gloss.split()) > 2:
        return False, "gloss_too_long"
    return True, None

def main() -> None:
    with SRC.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    kept: list[dict[str, str]] = []
    reject_stats: dict[str, int] = {}

    for row in rows:
        ok, reason = keep(row)
        if ok:
            kept.append(row)
        else:
            reject_stats[reason or "unknown"] = reject_stats.get(reason or "unknown", 0) + 1

    kept.sort(key=lambda r: (parse_rank(r.get("freq_rank")), norm(r.get("lemma"))))
    kept = kept[:MAX_ROWS]

    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["external_key", "lemma", "pos", "level", "freq_rank", "ru_gloss", "notes"],
        )
        writer.writeheader()
        for row in kept:
            writer.writerow({
                "external_key": row.get("external_key", ""),
                "lemma": row.get("lemma", ""),
                "pos": row.get("pos", ""),
                "level": row.get("level", ""),
                "freq_rank": row.get("freq_rank", ""),
                "ru_gloss": row.get("ru_gloss", ""),
                "notes": "pilot_safe_subset",
            })

    print(f"written={OUT}")
    print(f"input_rows={len(rows)}")
    print(f"kept_rows={len(kept)}")
    print("reject_stats:")
    for k in sorted(reject_stats):
        print(f"{k}={reject_stats[k]}")

if __name__ == "__main__":
    main()
