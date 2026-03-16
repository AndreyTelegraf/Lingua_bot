#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

DB_PATH = Path("data/lingua_staging.db")
TMP_DIR = Path("tmp")
BACKUP_DIR = TMP_DIR / "db_backups"
REPORT_PATH = TMP_DIR / "fix_2k_adjectives_active_semantic_suspects_staging_report.json"

CANONICAL = {
    "parecer": "казаться",
    "enviar": "послать",
    "beber": "пить",
    "melhorar": "улучшать",
    "andar": "ходить",
}


def now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def fetch_target_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    placeholders = ", ".join("?" for _ in CANONICAL)
    return conn.execute(
        f"""
        SELECT
          vi.id,
          vi.lemma,
          vi.correct_answer,
          vi.pos,
          vi.bin_name,
          vi.freq_rank,
          vi.is_active,
          vi.topic_tag,
          COUNT(vc.id) AS choice_count,
          SUM(CASE WHEN COALESCE(vc.is_correct, 0) = 1 THEN 1 ELSE 0 END) AS correct_count
        FROM vocab_items vi
        LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.pos = 'adjective'
          AND vi.bin_name = '2K'
          AND vi.is_active = 1
          AND vi.lemma IN ({placeholders})
        GROUP BY
          vi.id, vi.lemma, vi.correct_answer, vi.pos, vi.bin_name,
          vi.freq_rank, vi.is_active, vi.topic_tag
        ORDER BY vi.freq_rank DESC, vi.lemma ASC, vi.id ASC
        """,
        tuple(CANONICAL.keys()),
    ).fetchall()


def set_correct_answer_and_choices(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    new_correct_answer: str,
) -> dict:
    conn.row_factory = sqlite3.Row

    choices = conn.execute(
        """
        SELECT id, choice_text, is_correct, position_index
        FROM vocab_choices
        WHERE item_id = ?
        ORDER BY position_index, id
        """,
        (item_id,),
    ).fetchall()

    if len(choices) != 6:
        raise RuntimeError(f"item_id={item_id}: expected 6 choices, got {len(choices)}")

    correct_rows = [r for r in choices if int(r["is_correct"] or 0) == 1]
    if len(correct_rows) != 1:
        raise RuntimeError(f"item_id={item_id}: expected 1 correct choice, got {len(correct_rows)}")

    old_correct_choice = correct_rows[0]

    conn.execute(
        "UPDATE vocab_items SET correct_answer = ? WHERE id = ?",
        (new_correct_answer, item_id),
    )
    conn.execute(
        "UPDATE vocab_choices SET choice_text = ? WHERE id = ?",
        (new_correct_answer, int(old_correct_choice["id"])),
    )

    after = conn.execute(
        """
        SELECT id, choice_text, is_correct, position_index
        FROM vocab_choices
        WHERE item_id = ?
        ORDER BY position_index, id
        """,
        (item_id,),
    ).fetchall()

    return {
        "old_correct_choice_id": int(old_correct_choice["id"]),
        "old_correct_choice_text": str(old_correct_choice["choice_text"]),
        "new_correct_choice_text": new_correct_answer,
        "after_choices": [
            {
                "id": int(r["id"]),
                "choice_text": str(r["choice_text"]),
                "is_correct": int(r["is_correct"] or 0),
                "position_index": int(r["position_index"] or 0),
            }
            for r in after
        ],
    }


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    backup_path = BACKUP_DIR / f"lingua_staging_before_fix_2k_adjectives_semantics_{now_stamp()}.db"
    shutil.copy2(DB_PATH, backup_path)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    before_rows = [dict(r) for r in fetch_target_rows(conn)]
    applied = []

    for row in before_rows:
        lemma = str(row["lemma"])
        expected = CANONICAL[lemma]
        current = str(row["correct_answer"])
        item_id = int(row["id"])

        patch_info = set_correct_answer_and_choices(
            conn,
            item_id=item_id,
            new_correct_answer=expected,
        )

        applied.append(
            {
                "id": item_id,
                "lemma": lemma,
                "freq_rank": int(row["freq_rank"]) if row["freq_rank"] is not None else None,
                "old_correct_answer": current,
                "new_correct_answer": expected,
                **patch_info,
            }
        )

    conn.commit()

    after_rows = [dict(r) for r in fetch_target_rows(conn)]

    report = {
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "canonical_map": CANONICAL,
        "before_rows": before_rows,
        "applied": applied,
        "after_rows": after_rows,
    }

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("===== FIX 2K ADJECTIVES ACTIVE SEMANTIC SUSPECTS =====")
    print(json.dumps(
        {
            "db_path": str(DB_PATH),
            "backup_path": str(backup_path),
            "updated_count": len(applied),
            "report_path": str(REPORT_PATH),
        },
        ensure_ascii=False,
        indent=2,
    ))

    print("\n===== APPLIED =====")
    for row in applied:
        print(json.dumps(row, ensure_ascii=False))

    conn.close()


if __name__ == "__main__":
    main()
