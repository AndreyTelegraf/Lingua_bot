from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

BASE = Path("/home/andrey/Projects/lingua_bot_v2")
DB = BASE / "data" / "lingua_staging.db"
TS = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
OUT_DIR = BASE / "artifacts" / f"rebuild_keep_semantics_choices_{TS}"
BACKUP = OUT_DIR / f"lingua_staging_before_rebuild_keep_semantics_choices_{TS}.db"

TARGET_IDS = [163, 566]

def fetch_item(conn: sqlite3.Connection, item_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, lemma, correct_answer, pos, bin_name, freq_rank, is_active
        FROM vocab_items
        WHERE id = ?
        """,
        (item_id,),
    ).fetchone()

def fetch_pool(conn: sqlite3.Connection, *, pos: str, exclude_id: int, exclude_answers: set[str]) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT id, correct_answer, freq_rank
        FROM vocab_items
        WHERE is_active = 1
          AND pos = ?
          AND id != ?
        ORDER BY
          CASE WHEN freq_rank IS NULL THEN 1 ELSE 0 END,
          freq_rank ASC,
          id ASC
        """,
        (pos, exclude_id),
    ).fetchall()
    out = []
    seen = set()
    for r in rows:
        ans = (r["correct_answer"] or "").strip()
        if not ans or ans in exclude_answers or ans in seen:
            continue
        seen.add(ans)
        out.append(r)
    return out

def replace_choices(conn: sqlite3.Connection, item_id: int, correct_answer: str, distractors: list[str]) -> None:
    conn.execute("DELETE FROM vocab_choices WHERE item_id = ?", (item_id,))
    choices = [correct_answer] + distractors[:5]
    for idx, txt in enumerate(choices):
        conn.execute(
            """
            INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (item_id, txt, 1 if idx == 0 else 0, idx),
        )

def audit_item(conn: sqlite3.Connection, item_id: int) -> dict:
    rows = conn.execute(
        """
        SELECT choice_text, is_correct, position_index
        FROM vocab_choices
        WHERE item_id = ?
        ORDER BY position_index ASC, id ASC
        """,
        (item_id,),
    ).fetchall()
    texts = [str(r["choice_text"] or "") for r in rows]
    return {
        "item_id": item_id,
        "choice_count": len(rows),
        "correct_count": sum(int(r["is_correct"] or 0) for r in rows),
        "unique_count": len(set(texts)),
        "choices": texts,
    }

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DB, BACKUP)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rebuilt = []
    skipped = []

    for item_id in TARGET_IDS:
        item = fetch_item(conn, item_id)
        if item is None:
            skipped.append({"id": item_id, "reason": "missing_item"})
            continue
        if int(item["is_active"] or 0) != 1:
            skipped.append({"id": item_id, "reason": "inactive_item"})
            continue

        pos = str(item["pos"] or "").strip()
        correct_answer = str(item["correct_answer"] or "").strip()
        if not pos or not correct_answer:
            skipped.append({"id": item_id, "reason": "missing_pos_or_answer"})
            continue

        bad_now = {
            "aaa", "m", "словo",
            correct_answer,
        }

        pool = fetch_pool(conn, pos=pos, exclude_id=item_id, exclude_answers=bad_now)
        distractors = [str(r["correct_answer"]) for r in pool[:5]]

        if len(distractors) < 5:
            skipped.append({"id": item_id, "reason": f"not_enough_distractors:{len(distractors)}"})
            continue

        replace_choices(conn, item_id, correct_answer, distractors)
        rebuilt.append(
            {
                "id": item_id,
                "lemma": item["lemma"],
                "correct_answer": correct_answer,
                "pos": pos,
                "bin_name": item["bin_name"],
            }
        )

    conn.commit()

    audits = [audit_item(conn, item_id) for item_id in TARGET_IDS if fetch_item(conn, item_id) is not None]

    summary = {
        "output_dir": str(OUT_DIR),
        "db_backup": str(BACKUP),
        "target_ids": TARGET_IDS,
        "rebuilt_count": len(rebuilt),
        "skipped_count": len(skipped),
        "rebuilt": rebuilt,
        "skipped": skipped,
        "post_audit": audits,
    }

    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with (OUT_DIR / "rebuilt.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "lemma", "correct_answer", "pos", "bin_name"])
        writer.writeheader()
        writer.writerows(rebuilt)

    with (OUT_DIR / "skipped.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "reason"])
        writer.writeheader()
        writer.writerows(skipped)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    conn.close()

if __name__ == "__main__":
    main()
