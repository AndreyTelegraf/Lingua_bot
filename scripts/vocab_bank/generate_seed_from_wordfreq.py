from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

from wordfreq import top_n_list

OUT = Path("data/sources/pilot_ptpt_001.csv")
LIMIT = 12000

RE_HAS_DIGIT = re.compile(r"\d")
RE_BAD_CHARS = re.compile(r"[^a-zà-ÿçáéíóúâêôãõü\-]", re.IGNORECASE)
RE_TOO_SHORT = re.compile(r"^.{0,1}$")

BLOCKLIST_EXACT = {
    "deus","jesus","cristo","maria",
    "lisboa","porto","brasil","angola","moçambique",
    "ônibus","onibus","machimbombo",
}

BLOCKLIST_SUBSTR = {
    "igrej","santo","santa","padre","bispo","freira","mosteir",
    "catedral","paróqui","paroqui","oração","oracao","diocese",
    "evangelh","apóstol","apostol","liturg","sacrament","pecad",
    "milagr","relíqui","reliqui",
}

def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip().lower()

def looks_ok(word: str) -> bool:
    w = norm(word)

    if not w:
        return False
    if RE_TOO_SHORT.search(w):
        return False
    if RE_HAS_DIGIT.search(w):
        return False
    if RE_BAD_CHARS.search(w):
        return False
    if w.startswith("-") or w.endswith("-"):
        return False
    if "--" in w:
        return False

    if w in BLOCKLIST_EXACT:
        return False

    for x in BLOCKLIST_SUBSTR:
        if x in w:
            return False

    return True


def main():
    raw = top_n_list("pt", LIMIT * 3)

    seen=set()
    rows=[]
    rank=0

    for token in raw:
        rank+=1
        lemma = norm(token)

        if lemma in seen:
            continue

        if not looks_ok(lemma):
            continue

        seen.add(lemma)

        external_key = f"wfpt-{len(rows)+1:05d}"

        rows.append((
            external_key,
            lemma,
            "",
            "",
            str(rank),
            "",
            "seed_from_wordfreq_pt",
        ))

        if len(rows) >= LIMIT:
            break


    OUT.parent.mkdir(parents=True, exist_ok=True)

    with OUT.open("w",encoding="utf-8",newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "external_key",
            "lemma",
            "pos",
            "level",
            "freq_rank",
            "ru_gloss",
            "notes"
        ])
        writer.writerows(rows)

    print("written=",OUT)
    print("rows=",len(rows))


if __name__=="__main__":
    main()
