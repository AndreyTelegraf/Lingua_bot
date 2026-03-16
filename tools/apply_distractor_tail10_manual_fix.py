from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"
CSV_PATH = BASE / "tools" / "distractor_tail10_manual_fix_filled_20260316.csv"

TS = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
OUT_DIR = BASE / "artifacts" / f"distractor_tail10_manual_apply_{TS}"
BACKUP = OUT_DIR / f"lingua_staging_before_distractor_tail10_manual_apply_{TS}.db"

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, BACKUP)

    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8", newline="")))
    target_rows = [r for r in rows if (r.get("manual_action") or "").strip() == "REPLACE_CHOICES"]

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    applied = []
    skipped = []

    for r in target_rows:
        item_id = int(r["id"])
        choices = [r.get(f"new_choice_{i}", "").strip() for i in range(1, 7)]

        if len([x for x in choices if x]) != 6:
            skipped.append({"id": item_id, "reason": "need_exactly_6_choices"})
            continue

        if len(set(choices)) != 6:
            skipped.append({"id": item_id, "reason": "duplicate_choices"})
            continue

        correct_answer = (r.get("correct_answer") or "").strip()
        if correct_answer not in choices:
            skipped.append({"id": item_id, "reason": "correct_answer_missing_from_choices"})
            continue

        conn.execute("DELETE FROM vocab_choices WHERE item_id = ?", (item_id,))
        correct_slot = choices.index(correct_answer)

        for idx, txt in enumerate(choices):
            conn.execute(
                """
                INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (item_id, txt, 1 if idx == correct_slot else 0, idx),
            )

        applied.append({
            "id": item_id,
            "lemma": r.get("lemma", ""),
            "correct_answer": correct_answer,
            "choices": choices,
        })

    conn.commit()

    sanity = []
    for r in applied:
        item_id = r["id"]
        db_rows = conn.execute(
            """
            SELECT choice_text, is_correct, position_index
            FROM vocab_choices
            WHERE item_id = ?
            ORDER BY position_index ASC, id ASC
            """,
            (item_id,),
        ).fetchall()
        sanity.append({
            "id": item_id,
            "choice_count": len(db_rows),
            "correct_count": sum(int(x["is_correct"] or 0) for x in db_rows),
            "unique_count": len(set(str(x["choice_text"] or "") for x in db_rows)),
            "choices": [str(x["choice_text"] or "") for x in db_rows],
        })

    summary = {
        "source_csv": str(CSV_PATH),
        "output_dir": str(OUT_DIR),
        "db_backup": str(BACKUP),
        "target_count": len(target_rows),
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "applied_ids": [x["id"] for x in applied],
        "skipped": skipped,
        "sanity": sanity,
    }

    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    conn.close()

if __name__ == "__main__":
    main()
