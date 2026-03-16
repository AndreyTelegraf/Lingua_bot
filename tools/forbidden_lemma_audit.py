from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"
TS = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
OUT_DIR = BASE / "artifacts" / f"forbidden_lemma_audit_{TS}"

LAT = re.compile(r"[A-Za-z]")
CYR = re.compile(r"[А-Яа-яЁё]")

def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def translitish_similarity(a: str, b: str) -> float:
    repl = str.maketrans({
        "a":"а","b":"б","c":"к","d":"д","e":"е","f":"ф","g":"г","h":"х","i":"и","j":"ж","k":"к","l":"л",
        "m":"м","n":"н","o":"о","p":"п","q":"к","r":"р","s":"с","t":"т","u":"у","v":"в","w":"в","x":"кс","y":"и","z":"з",
    })
    a2 = norm(a).translate(repl)
    b2 = norm(b)
    common = sum(1 for x, y in zip(a2, b2) if x == y)
    return common / max(len(a2), len(b2), 1)

def is_likely_proper_name(lemma: str, translation: str) -> bool:
    l = norm(lemma)
    t = norm(translation)
    explicit = {
        "nicarágua", "nice", "humberto", "cristóvão", "vasco", "pedro",
        "isaías", "jaime", "mateus", "lourenço", "lúcio", "júlio",
    }
    if l in explicit:
        return True
    if " " not in l and len(l) >= 4 and translitish_similarity(l, t) >= 0.82:
        # strong translit + likely name/toponym pattern
        return True
    return False

def is_forbidden_cognate(lemma: str, translation: str) -> bool:
    l = norm(lemma)
    t = norm(translation)
    score = translitish_similarity(l, t)
    if score < 0.82:
        return False
    keep_whitelist = {"sul", "inferno", "visto", "bolsa"}
    if l in keep_whitelist:
        return False
    return True

def suspicious_pos(lemma: str, translation: str, pos: str) -> list[str]:
    l = norm(lemma)
    t = norm(translation)
    out = []
    if pos == "noun":
        if l.endswith("mente"):
            out.append("lemma_looks_adverb_but_pos_noun")
        if l in {"mentiroso", "ignorante", "delgado", "muscular", "rígido", "acelerado"}:
            out.append("lemma_looks_adj_but_pos_noun")
        if l in {"escondidas"}:
            out.append("lemma_looks_non_noun")
    return out

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    items = conn.execute("""
        SELECT id, lemma, question_text, correct_answer, pos, bin_name, level, freq_rank
        FROM vocab_items
        WHERE is_active = 1
        ORDER BY
            CASE bin_name
                WHEN '1K' THEN 1
                WHEN '2K' THEN 2
                WHEN '5K' THEN 3
                WHEN '10K' THEN 4
                WHEN '20K' THEN 5
                ELSE 99
            END,
            CASE WHEN freq_rank IS NULL THEN 1 ELSE 0 END,
            freq_rank,
            id
    """).fetchall()

    rows = []
    flags_count = Counter()

    for r in items:
        lemma = str(r["lemma"] or "")
        ans = str(r["correct_answer"] or "")
        pos = str(r["pos"] or "")
        flags = []
        notes = []

        score = translitish_similarity(lemma, ans)

        if is_likely_proper_name(lemma, ans):
            flags.append("PROPER_NAME_OR_TOPONYM")
            notes.append(f"translit_score={score:.3f}")

        if is_forbidden_cognate(lemma, ans):
            flags.append("FORBIDDEN_COGNATE")
            notes.append(f"translit_score={score:.3f}")

        pos_flags = suspicious_pos(lemma, ans, pos)
        flags.extend(pos_flags)
        notes.extend(pos_flags)

        triage = "PASS"
        if "PROPER_NAME_OR_TOPONYM" in flags or "FORBIDDEN_COGNATE" in flags:
            triage = "REJECT"
        elif pos_flags:
            triage = "REVIEW"

        for f in flags:
            flags_count[f] += 1

        rows.append({
            "id": r["id"],
            "lemma": lemma,
            "question_text": r["question_text"],
            "correct_answer": ans,
            "pos": pos,
            "bin_name": r["bin_name"],
            "level": r["level"],
            "freq_rank": r["freq_rank"],
            "translit_score": f"{score:.3f}",
            "audit_flags": ";".join(flags),
            "audit_notes": " || ".join(notes),
            "triage_status": triage,
        })

    full = OUT_DIR / "forbidden_lemma_audit_full.csv"
    rej = OUT_DIR / "forbidden_lemma_reject.csv"
    rev = OUT_DIR / "forbidden_lemma_review.csv"

    fieldnames = list(rows[0].keys()) if rows else []

    with full.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    reject_rows = [x for x in rows if x["triage_status"] == "REJECT"]
    review_rows = [x for x in rows if x["triage_status"] == "REVIEW"]

    with rej.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(reject_rows)

    with rev.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(review_rows)

    summary = {
        "total_active_items": len(rows),
        "reject_count": len(reject_rows),
        "review_count": len(review_rows),
        "flag_counts": dict(flags_count),
        "output_dir": str(OUT_DIR),
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
