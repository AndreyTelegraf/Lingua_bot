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

BLOCKED_SUBSTR = [
    "feminine of ",
    "masculine of ",
    "plural of ",
    "alternative form of ",
    "ellipsis of ",
    "misspelling",
    "obsolete spelling",
    "pre-reform spelling",
    "surname",
    "municipality",
    "river in ",
    "slavic tribe",
    "script letter",
    "letter ",
    "nickname",
]

def norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def existing_nouns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT lower(trim(lemma)) FROM vocab_items WHERE pos='noun'").fetchall()
    return {str(r[0]) for r in rows}

def blocked_gloss(gloss: str) -> bool:
    low = norm(gloss)
    return any(x in low for x in BLOCKED_SUBSTR)

def main() -> None:
    outdir = ART / f"noun_remediation_report_v2_{time.strftime('%Y%m%d_%H%M%S')}"
    outdir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    present = existing_nouns(conn)
    conn.close()

    needs_manual = []
    already_present = []
    blocked = []
    skipped_shape = []

    with SRC.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            lemma = (raw.get("lemma") or "").strip()
            pos = (raw.get("pos") or "").strip()
            gloss = (raw.get("ru_gloss") or "").strip()
            freq_rank = int((raw.get("freq_rank") or "999999").strip() or "999999")
            source_file = (raw.get("source_file") or "").strip()

            if pos != "noun":
                continue

            row = {
                "lemma": lemma,
                "pos": pos,
                "freq_rank": freq_rank,
                "ru_gloss": gloss,
                "source_file": source_file,
            }

            if norm(lemma) in present:
                already_present.append(row)
                continue

            if "-" in lemma or lemma[:1].isupper() or len(lemma) <= 2:
                skipped_shape.append(row)
                continue

            if blocked_gloss(gloss):
                blocked.append(row)
                continue

            needs_manual.append(row)

    needs_manual.sort(key=lambda x: (x["freq_rank"], x["lemma"]))

    export_rows = needs_manual[:400]
    stub = {row["lemma"]: "" for row in export_rows}

    (outdir / "top400_needs_manual_ru_v2.json").write_text(
        json.dumps(export_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (outdir / "manual_ru_map_stub_v4.json").write_text(
        json.dumps(stub, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = {
        "source_csv": str(SRC),
        "counts": {
            "needs_manual_ru_total": len(needs_manual),
            "top400_exported": len(export_rows),
            "already_present": len(already_present),
            "blocked_source_gloss": len(blocked),
            "skip_shape": len(skipped_shape),
        },
        "top50_needs_manual_ru": export_rows[:50],
        "artifacts": {
            "top400_needs_manual_ru_v2": str(outdir / "top400_needs_manual_ru_v2.json"),
            "manual_ru_map_stub_v4": str(outdir / "manual_ru_map_stub_v4.json"),
        },
    }

    (outdir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(outdir / "summary.json")

if __name__ == "__main__":
    main()
