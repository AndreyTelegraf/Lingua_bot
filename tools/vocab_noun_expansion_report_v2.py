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
    "eye dialect",
    "abbreviation",
    "suffix",
]

MANUAL_RU = {
    "pelo": "волос",
    "mesmo": "то же самое",
    "tudo": "всё",
    "agora": "настоящее время",
    "era": "эра",
    "vez": "раз",
    "coisa": "вещь",
    "parte": "часть",
    "forma": "форма",
    "nome": "имя",
    "caso": "случай",
    "história": "история",
    "grupo": "группа",
    "cara": "лицо",
    "lado": "сторона",
    "direito": "право",
    "medo": "страх",
    "força": "сила",
    "linha": "линия",
    "modo": "режим",
    "valor": "значение",
    "efeito": "эффект",
    "minuto": "минута",
}

def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]

def existing_lemma_pos(conn: sqlite3.Connection) -> set[tuple[str, str]]:
    rows = conn.execute("SELECT lower(trim(lemma)), pos FROM vocab_items").fetchall()
    return {(str(a), str(b)) for a, b in rows}

def classify(row: dict[str, str], existing: set[tuple[str, str]]) -> tuple[str, list[str]]:
    lemma = row["lemma"]
    pos = row["pos"]
    gloss = row["ru_gloss"]
    issues: list[str] = []

    if (norm(lemma), pos) in existing:
        return "already_present", issues

    if not lemma or pos != "noun":
        issues.append("bad_pos_or_lemma")
        return "reject", issues

    low = norm(gloss)
    if not low:
        issues.append("missing_gloss")
        if lemma in MANUAL_RU:
            return "needs_choice_pack_only", issues
        return "needs_full_manual", issues

    if any(x in low for x in BAD_SUBSTR):
        issues.append("bad_gloss_pattern")
        if lemma in MANUAL_RU:
            return "needs_choice_pack_only", issues
        return "needs_full_manual", issues

    if len(lemma) <= 2:
        issues.append("short_lemma")
    if "-" in lemma:
        issues.append("hyphen_lemma")
    if lemma[:1].isupper():
        issues.append("capitalized_lemma")

    if lemma in MANUAL_RU:
        return "needs_choice_pack_only", issues

    return "needs_ru_and_choices", issues

def main() -> None:
    outdir = ART / f"noun_expansion_report_v2_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    existing = existing_lemma_pos(conn)
    conn.close()

    counts: dict[str, int] = {}
    buckets: dict[str, list[dict]] = {}
    rows_out: list[dict] = []

    with SRC.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            row = {
                "lemma": (r.get("lemma") or "").strip(),
                "pos": (r.get("pos") or "").strip(),
                "freq_rank": int((r.get("freq_rank") or "999999").strip() or "999999"),
                "ru_gloss": (r.get("ru_gloss") or "").strip(),
                "source_file": (r.get("source_file") or "").strip(),
            }
            if row["pos"] != "noun":
                continue
            status, issues = classify(row, existing)
            row["status"] = status
            row["issues"] = issues
            rows_out.append(row)
            counts[status] = counts.get(status, 0) + 1
            buckets.setdefault(status, []).append(row)

    for k in buckets:
        buckets[k].sort(key=lambda x: (x["freq_rank"], x["lemma"]))

    report = {
        "source_csv": str(SRC),
        "existing_vocab_items_checked": True,
        "counts": counts,
        "top_needs_choice_pack_only": buckets.get("needs_choice_pack_only", [])[:100],
        "top_needs_ru_and_choices": buckets.get("needs_ru_and_choices", [])[:100],
        "top_needs_full_manual": buckets.get("needs_full_manual", [])[:100],
        "top_already_present": buckets.get("already_present", [])[:30],
    }

    (outdir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "all_rows.json").write_text(json.dumps(rows_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
