#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/lingua_staging.db")
BACKUP_DIR = Path("tmp/db_backups")
REPORT_PATH = Path("tmp/fix_remaining_staging_bad_choices_report.json")


def classify_text(s: str | None) -> str:
    s = (s or "").strip()
    if not s:
        return "EMPTY"
    has_cyr = any("А" <= ch <= "я" or ch in "Ёё" for ch in s)
    has_lat = any(
        ("A" <= ch <= "Z") or ("a" <= ch <= "z") or ch in "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ"
        for ch in s
    )
    if has_cyr and has_lat:
        return "MIXED"
    if has_cyr:
        return "CYR"
    if has_lat:
        return "LAT"
    return "OTHER"


def audit(cur: sqlite3.Cursor) -> dict:
    rows = cur.execute(
        """
        SELECT vi.id, vi.correct_answer, vc.choice_text, vc.is_correct
        FROM vocab_items vi
        JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.is_active = 1
        ORDER BY vi.id, vc.position_index, vc.id
        """
    ).fetchall()

    by_item: dict[int, int] = {}
    for item_id, correct_answer, choice_text, is_correct in rows:
        by_item.setdefault(item_id, 0)
        if is_correct != 1 and classify_text(correct_answer) == "CYR" and classify_text(choice_text) in {"LAT", "MIXED"}:
            by_item[item_id] += 1

    return {
        "active_items_seen": len(by_item),
        "items_with_lat_distractor_when_answer_cyr": sum(1 for v in by_item.values() if v > 0),
        "total_bad_distractors": sum(by_item.values()),
    }


def find_bad_rows(cur: sqlite3.Cursor) -> list[sqlite3.Row]:
    cur.row_factory = sqlite3.Row
    return cur.execute(
        """
        SELECT
          vi.id AS item_id,
          vi.lemma,
          vi.pos,
          vi.bin_name,
          vi.freq_rank,
          vi.correct_answer,
          vc.id AS choice_id,
          vc.choice_text,
          vc.position_index
        FROM vocab_items vi
        JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.is_active = 1
          AND vc.is_correct = 0
        ORDER BY vi.id, vc.position_index, vc.id
        """
    ).fetchall()


def pick_replacement(cur: sqlite3.Cursor, *, item_id: int, pos: str, bin_name: str, freq_rank: int | None, existing_choices: set[str], correct_answer: str) -> str:
    rows = cur.execute(
        """
        SELECT id, correct_answer, freq_rank
        FROM vocab_items
        WHERE is_active = 1
          AND pos = ?
          AND bin_name = ?
        ORDER BY
          CASE WHEN freq_rank IS NULL THEN 1 ELSE 0 END,
          ABS(COALESCE(freq_rank, 999999) - COALESCE(?, 999999)),
          id
        """,
        (pos, bin_name, freq_rank),
    ).fetchall()

    for candidate_id, candidate_answer, candidate_freq_rank in rows:
        if not candidate_answer:
            continue
        if classify_text(candidate_answer) != "CYR":
            continue
        if candidate_answer == correct_answer:
            continue
        if candidate_answer in existing_choices:
            continue
        return candidate_answer

    rows = cur.execute(
        """
        SELECT id, correct_answer, freq_rank
        FROM vocab_items
        WHERE is_active = 1
          AND pos = ?
        ORDER BY
          CASE WHEN freq_rank IS NULL THEN 1 ELSE 0 END,
          ABS(COALESCE(freq_rank, 999999) - COALESCE(?, 999999)),
          id
        """,
        (pos, freq_rank),
    ).fetchall()

    for candidate_id, candidate_answer, candidate_freq_rank in rows:
        if not candidate_answer:
            continue
        if classify_text(candidate_answer) != "CYR":
            continue
        if candidate_answer == correct_answer:
            continue
        if candidate_answer in existing_choices:
            continue
        return candidate_answer

    raise RuntimeError(f"No replacement found for item_id={item_id}")


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"{DB_PATH.stem}_before_remaining_bad_choice_fix_{ts}.db"
    shutil.copy2(DB_PATH, backup_path)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    pre_audit = audit(cur)

    raw_rows = find_bad_rows(cur)
    bad_rows = []
    for r in raw_rows:
        if classify_text(r["correct_answer"]) == "CYR" and classify_text(r["choice_text"]) in {"LAT", "MIXED"}:
            bad_rows.append(dict(r))

    replacements = []

    for bad in bad_rows:
        item_id = bad["item_id"]
        existing_rows = cur.execute(
            """
            SELECT choice_text
            FROM vocab_choices
            WHERE item_id = ?
            ORDER BY position_index, id
            """,
            (item_id,),
        ).fetchall()

        existing_choices = {row["choice_text"] for row in existing_rows if row["choice_text"]}
        existing_choices.discard(bad["choice_text"])

        replacement = pick_replacement(
            cur,
            item_id=item_id,
            pos=bad["pos"],
            bin_name=bad["bin_name"],
            freq_rank=bad["freq_rank"],
            existing_choices=existing_choices,
            correct_answer=bad["correct_answer"],
        )
        replacements.append(
            {
                **bad,
                "replacement_text": replacement,
            }
        )

    cur.execute("BEGIN")
    for row in replacements:
        cur.execute(
            "UPDATE vocab_choices SET choice_text = ? WHERE id = ?",
            (row["replacement_text"], row["choice_id"]),
        )
    conn.commit()

    post_audit = audit(cur)

    verify_rows = cur.execute(
        """
        SELECT
          vi.id AS item_id,
          vi.lemma,
          vi.correct_answer,
          vc.id AS choice_id,
          vc.choice_text,
          vc.is_correct,
          vc.position_index
        FROM vocab_items vi
        JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.id IN (
          SELECT DISTINCT vi2.id
          FROM vocab_items vi2
          JOIN vocab_choices vc2 ON vc2.item_id = vi2.id
          WHERE vi2.is_active = 1
        )
        ORDER BY vi.id, vc.position_index, vc.id
        LIMIT 120
        """
    ).fetchall()

    report = {
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "pre_audit": pre_audit,
        "bad_rows_found": len(bad_rows),
        "replacements": replacements,
        "post_audit": post_audit,
        "verify_sample": [dict(r) for r in verify_rows[:60]],
    }

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
