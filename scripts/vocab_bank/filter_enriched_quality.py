from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

SRC = Path("data/sources/pilot_ptpt_001_enriched.csv")
OUT = Path("data/sources/pilot_ptpt_001_enriched_qc.csv")

ALLOWED_POS = {"noun", "verb", "adjective", "adverb"}

BAD_LEMMA_EXACT = {
    "abel", "paulo", "aaron", "abril", "janeiro",
    "nba", "nokia", "owen", "messi", "nov",
}

BAD_LEMMA_SUBSTR = {
    "cristo", "jesus", "deus", "igrej", "santo", "santa",
    "padre", "bispo", "freira", "mosteir", "catedral",
    "ônibus", "onibus", "machimbombo",
}

BAD_RU_GLOSS_EXACT = {
    "мент",
    "фес",
}

BAD_RU_GLOSS_SUBSTR = {
    "сленг",
}

# Слишком подозрительные пары, которые уже всплыли в выводе
BAD_PAIRS = {
    ("pensar", "найти"),
    ("segurança", "сохранность"),
    ("ponto", "балл"),
    ("política", "курс"),
    ("tempo", "час"),
}

def norm(s: str | None) -> str:
    if s is None:
        return ""
    return unicodedata.normalize("NFC", s).strip().lower()

def good_lemma(lemma: str) -> bool:
    x = norm(lemma)
    if not x:
        return False
    if len(x) < 3:
        return False
    if x in BAD_LEMMA_EXACT:
        return False
    if any(b in x for b in BAD_LEMMA_SUBSTR):
        return False
    return True

def good_gloss(gloss: str) -> bool:
    x = norm(gloss)
    if not x:
        return False
    if len(x) < 2:
        return False
    if len(x.split()) > 3:
        return False
    if any(ch in x for ch in ",;/()[]"):
        return False
    if x in BAD_RU_GLOSS_EXACT:
        return False
    if any(b in x for b in BAD_RU_GLOSS_SUBSTR):
        return False
    return True

def main() -> None:
    with SRC.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    reject_stats: dict[str, int] = {}

    for row in rows:
        lemma = norm(row.get("lemma"))
        pos = norm(row.get("pos"))
        gloss = norm(row.get("ru_gloss"))

        reason = None

        if not gloss:
            reason = "missing_gloss"
        elif pos not in ALLOWED_POS:
            reason = "bad_pos"
        elif not good_lemma(lemma):
            reason = "bad_lemma"
        elif not good_gloss(gloss):
            reason = "bad_gloss"
        elif (lemma, gloss) in BAD_PAIRS:
            reason = "bad_pair"

        if reason is not None:
            reject_stats[reason] = reject_stats.get(reason, 0) + 1
            continue

        out_rows.append({
            "external_key": row.get("external_key", ""),
            "lemma": row.get("lemma", ""),
            "pos": row.get("pos", ""),
            "level": row.get("level", ""),
            "freq_rank": row.get("freq_rank", ""),
            "ru_gloss": row.get("ru_gloss", ""),
            "notes": "enriched_qc_pass",
        })

    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["external_key", "lemma", "pos", "level", "freq_rank", "ru_gloss", "notes"],
        )
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"written={OUT}")
    print(f"input_rows={len(rows)}")
    print(f"output_rows={len(out_rows)}")
    print("reject_stats:")
    for k in sorted(reject_stats):
        print(f"{k}={reject_stats[k]}")

if __name__ == "__main__":
    main()
