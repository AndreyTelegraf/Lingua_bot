from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

SRC = Path("data/sources/pilot_ptpt_001.csv")
OUT = Path("data/sources/pilot_ptpt_001_shortlist.csv")

FUNCTION_WORDS = {
    "de","do","da","dos","das","dum","duma",
    "a","o","os","as","ao","aos",
    "e","ou","mas","nem","que","se","como","porque","porquê","por que",
    "em","no","na","nos","nas",
    "por","para","pra","com","sem","sob","sobre","entre","até","desde","após","apos","contra",
    "um","uma","uns","umas",
    "eu","tu","ele","ela","nós","nos","vós","vos","vocês","voces","eles","elas","você","voce",
    "me","te","lhe","lhes","nos","vos","mim","ti","si","consigo","comigo","contigo",
    "meu","minha","meus","minhas","teu","tua","teus","tuas","seu","sua","seus","suas","nosso","nossa","nossos","nossas",
    "isto","isso","aquilo","este","esta","estes","estas","esse","essa","esses","essas","aquele","aquela","aqueles","aquelas",
    "já","ja","não","nao","sim","só","so","também","tambem","ainda","então","entao","muito","muita","muitos","muitas",
    "pouco","pouca","poucos","poucas","mais","menos","tão","tao","toda","todo","todos","todas",
    "ser","estar","ter","haver","ir","vir","dar","fazer","dizer","poder",
    "foi","era","são","sao","tem","têm","tinha","vai","está","esta"
}

BAD_EXACT = {
    "lisboa","porto","brasil","angola","moçambique","mozambique",
    "messi","owen","nokia","nba","nsa","nov"
}

BAD_SUBSTR = {
    "igrej","santo","santa","padre","bispo","freira","mosteir","catedral","paroqui","paróqui",
    "oração","oracao","diocese","evangelh","apostol","apóstol","liturg","sacrament",
    "ônibus","onibus","machimbombo"
}

def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip().lower()

def is_good_lemma(lemma: str) -> bool:
    w = norm(lemma)
    if not w:
        return False
    if len(w) < 3:
        return False
    if w in FUNCTION_WORDS:
        return False
    if w in BAD_EXACT:
        return False
    if any(x in w for x in BAD_SUBSTR):
        return False
    return True

def main() -> None:
    with SRC.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    for row in rows:
        lemma = norm(row["lemma"])
        if not is_good_lemma(lemma):
            continue

        out_rows.append({
            "external_key": row["external_key"],
            "lemma": lemma,
            "pos": row.get("pos", ""),
            "level": row.get("level", ""),
            "freq_rank": row.get("freq_rank", ""),
            "ru_gloss": row.get("ru_gloss", ""),
            "notes": "shortlisted_from_wordfreq_seed",
        })

    with OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["external_key","lemma","pos","level","freq_rank","ru_gloss","notes"]
        )
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"written={OUT}")
    print(f"rows={len(out_rows)}")

if __name__ == "__main__":
    main()
