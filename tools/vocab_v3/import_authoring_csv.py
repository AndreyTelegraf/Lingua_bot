from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

try:
    from tools.vocab_v3.validate_authoring_csv import validate_path
except ModuleNotFoundError:
    from validate_authoring_csv import validate_path

DB = "data/lingua_staging.db"

def fail(msg: str) -> None:
    raise SystemExit(f"FAIL: {msg}")

def _parse_args() -> tuple[Path, str]:
    args = sys.argv[1:]
    db_path = DB

    if len(args) == 3 and args[0] == "--db":
        db_path = args[1]
        csv_path = Path(args[2])
    elif len(args) == 1:
        csv_path = Path(args[0])
    else:
        fail("usage: import_authoring_csv.py [--db <db_path>] <csv_path>")

    return csv_path, db_path

def main() -> None:
    path, db_path = _parse_args()
    if not path.exists():
        fail(f"missing file: {path}")

    # validate first (fail-fast)
    validate_path(path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for row in rows:
        cur.execute("""
        INSERT INTO vocab_certified_inventory_v3 (
            lemma, question_text, correct_answer,
            pos, bin_name, is_active,
            freq_rank, level, audit_status,
            source_note, author_note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row["lemma"].strip(),
            row["prompt"].strip(),
            row["correct_choice"].strip(),
            row["pos"].strip(),
            row["bin_name"].strip(),
            1 if row["audit_status"] == "certified" else 0,
            None,
            None,
            row["audit_status"].strip(),
            row["source_note"].strip(),
            row["author_note"].strip(),
        ))
        item_id = cur.lastrowid

        choices = [
            (row["correct_choice"], 1),
            (row["distractor_1"], 0),
            (row["distractor_2"], 0),
            (row["distractor_3"], 0),
            (row["distractor_4"], 0),
            (row["distractor_5"], 0),
        ]

        for idx, (txt, is_correct) in enumerate(choices):
            cur.execute("""
            INSERT INTO vocab_choices_v3 (item_id, choice_text, is_correct, position_index)
            VALUES (?, ?, ?, ?)
            """, (item_id, txt.strip(), is_correct, idx))

    conn.commit()
    conn.close()

    print(f"PASS: imported {len(rows)} rows into vocab_certified_inventory_v3")

if __name__ == "__main__":
    main()
