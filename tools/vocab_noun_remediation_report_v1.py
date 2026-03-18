from __future__ import annotations

import csv
import json
import sqlite3
import time
from pathlib import Path

ROOT = Path("/home/andrey/Projects/lingua_bot_v2")
DB = ROOT / "data/lingua_staging.db"
SRC = ROOT / "data/sources/pilot_ptpt_001_nouns_external_clean.csv"
ART = ROOT / "artifacts"

EXISTING_MANUAL_RU = {
    "mais": "плюс",
    "ser": "существо",
    "são": "здоровый человек",
    "grande": "важная персона",
    "dois": "двойка",
    "nunca": "никогда",
    "todo": "целое",
    "novo": "новинка",
    "primeiro": "первый",
    "menos": "минус",
    "alguém": "человек",
    "falar": "говор",
    "tinha": "стригущий лишай",
    "boa": "хорошая новость",
    "três": "тройка",
    "meio": "середина",
    "mulher": "женщина",
    "ninguém": "никто",
    "foto": "фото",
    "saber": "знание",
    "conta": "счёт",
    "final": "конец",
    "hora": "час",
    "filho": "сын",
    "vídeo": "видео",
    "vão": "проём",
    "poder": "власть",
    "frente": "передняя часть",
    "tarde": "день",
    "local": "место",
    "público": "публика",
    "centro": "центр",
    "logo": "логотип",
    "feito": "поступок",
    "exemplo": "пример",
    "falta": "нехватка",
    "série": "серия",
    "causa": "причина",
    "uso": "использование",
    "cerca": "забор",
    "cinco": "пятёрка",
    "início": "начало",
    "claro": "просвет",
    "atenção": "внимание",
    "gosto": "вкус",
    "base": "основа",
    "fala": "речь",
    "passado": "прошлое",
}

BAD_SUBSTR = [
    "plural of ",
    "feminine of ",
    "masculine of ",
    "alternative form of ",
    "ellipsis of ",
    "nickname",
    "letter ",
    "script letter",
    "pre-reform spelling",
    "misspelling",
    "obsolete spelling",
    "surname",
    "slavic tribe",
    "municipality",
    "river in ",
    "river god",
    "world wide web",
    "greeting",
    "good morning",
    "good afternoon",
    "good evening",
    "new year",
    "afterlife",
    "beyond",
]

def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def existing_lemma_pos(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    rows = conn.execute("SELECT lower(trim(lemma)), pos FROM vocab_items").fetchall()
    return {(str(a), str(b)) for a, b in rows}

def classify(row: dict[str, str], existing: set[tuple[str, str]]) -> str:
    lemma = row["lemma"]
    gloss = row["ru_gloss"]
    if (norm(lemma), "noun") in existing:
        return "already_present"
    if lemma in EXISTING_MANUAL_RU:
        return "already_mapped"
    low = norm(gloss)
    if any(x in low for x in BAD_SUBSTR):
        return "blocked_source_gloss"
    if "-" in lemma:
        return "skip_hyphen"
    if lemma[:1].isupper():
        return "skip_capitalized"
    if len(lemma) <= 2:
        return "skip_short"
    return "needs_manual_ru"

def main() -> None:
    outdir = ART / f"noun_remediation_report_v1_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    existing = existing_lemma_pos(conn)
    conn.close()

    rows = []
    with SRC.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {
                "lemma": (raw.get("lemma") or "").strip(),
                "pos": (raw.get("pos") or "").strip(),
                "freq_rank": int((raw.get("freq_rank") or "999999").strip() or "999999"),
                "ru_gloss": (raw.get("ru_gloss") or "").strip(),
                "source_file": (raw.get("source_file") or "").strip(),
            }
            if row["pos"] != "noun":
                continue
            row["status"] = classify(row, existing)
            rows.append(row)

    manual = [r for r in rows if r["status"] == "needs_manual_ru"]
    manual.sort(key=lambda x: (x["freq_rank"], x["lemma"]))

    top150 = manual[:150]

    map_stub = {r["lemma"]: "" for r in top150}
    (outdir / "manual_ru_map_stub_v1.json").write_text(
        json.dumps(map_stub, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (outdir / "top150_needs_manual_ru.json").write_text(
        json.dumps(top150, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = {
        "source_csv": str(SRC),
        "counts": {
            "needs_manual_ru_total": len(manual),
            "top150_exported": len(top150),
            "already_present": sum(1 for r in rows if r["status"] == "already_present"),
            "already_mapped": sum(1 for r in rows if r["status"] == "already_mapped"),
            "blocked_source_gloss": sum(1 for r in rows if r["status"] == "blocked_source_gloss"),
            "skip_hyphen": sum(1 for r in rows if r["status"] == "skip_hyphen"),
            "skip_capitalized": sum(1 for r in rows if r["status"] == "skip_capitalized"),
            "skip_short": sum(1 for r in rows if r["status"] == "skip_short"),
        },
        "top50_needs_manual_ru": top150[:50],
        "artifacts": {
            "manual_ru_map_stub_v1": str(outdir / "manual_ru_map_stub_v1.json"),
            "top150_needs_manual_ru": str(outdir / "top150_needs_manual_ru.json"),
        },
    }

    (outdir / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
