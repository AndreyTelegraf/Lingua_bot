from __future__ import annotations

import csv
from pathlib import Path

SRC = Path("artifacts/unified_manual_review_queue.csv")
DST = Path("artifacts/unified_manual_review_decision_sheet.csv")

def main() -> int:
    if not SRC.exists():
        raise SystemExit(f"source not found: {SRC}")

    with SRC.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    fieldnames = [
        "pos",
        "id",
        "lemma",
        "correct_answer",
        "flags",
        "risk_score",
        "status",
        "suggested_action",
        "normalized_correct_answer",
        "explanation",
        "decision",
        "replacement_correct_answer",
        "notes",
    ]

    with DST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            decision = ""
            replacement = ""
            notes = ""

            if row["pos"] == "noun" and row["lemma"] in {"dona", "mulher"}:
                decision = "fix_correct_answer"
            elif row["pos"] == "verb" and row["lemma"] == "colar":
                decision = "fix_correct_answer"
                replacement = "клеить"
            elif row["pos"] == "verb" and row["lemma"] == "dever":
                decision = "keep"
            elif row["pos"] == "adjective" and row["lemma"] in {"bom", "mau"}:
                decision = "keep"
            elif row["pos"] == "adverb" and row["lemma"] in {"bem", "mal", "quase"}:
                decision = "keep"

            w.writerow({
                **row,
                "decision": decision,
                "replacement_correct_answer": replacement,
                "notes": notes,
            })

    print(DST)
    print("rows =", len(rows))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
