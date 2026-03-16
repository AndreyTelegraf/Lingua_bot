#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


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


def build_unique_lemma_map(cur: sqlite3.Cursor) -> dict[str, str]:
    rows = cur.execute(
        """
        SELECT lemma, correct_answer
        FROM vocab_items
        """
    ).fetchall()

    grouped: dict[str, set[str]] = {}
    for lemma, correct_answer in rows:
        grouped.setdefault(lemma, set()).add(correct_answer)

    return {lemma: list(vals)[0] for lemma, vals in grouped.items() if len(vals) == 1}


def audit(cur: sqlite3.Cursor) -> dict:
    rows = cur.execute(
        """
        SELECT
          vi.id,
          vi.correct_answer,
          vc.choice_text,
          vc.is_correct
        FROM vocab_items vi
        JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.is_active = 1
        ORDER BY vi.id, vc.position_index, vc.id
        """
    ).fetchall()

    by_item: dict[int, int] = {}
    for item_id, correct_answer, choice_text, is_correct in rows:
        if item_id not in by_item:
            by_item[item_id] = 0
        if is_correct != 1 and classify_text(correct_answer) == "CYR" and classify_text(choice_text) in {"LAT", "MIXED"}:
            by_item[item_id] += 1

    return {
        "active_items_seen": len(by_item),
        "items_with_lat_distractor_when_answer_cyr": sum(1 for v in by_item.values() if v > 0),
        "total_bad_distractors": sum(by_item.values()),
    }


def process_db(db_path_str: str) -> dict:
    db_path = Path(db_path_str)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    backup_dir = Path("tmp/db_backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"{db_path.stem}_before_choice_fix_{ts}.db"
    shutil.copy2(db_path, backup_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    pre_audit = audit(cur)
    lemma_map = build_unique_lemma_map(cur)

    candidate_rows = cur.execute(
        """
        SELECT id, choice_text
        FROM vocab_choices
        WHERE is_correct = 0
        """
    ).fetchall()

    updates: list[tuple[str, int]] = []
    unmapped = 0
    already_cyr_or_other = 0

    for row in candidate_rows:
        choice_id = row["id"]
        choice_text = row["choice_text"]
        cls = classify_text(choice_text)

        if cls not in {"LAT", "MIXED"}:
            already_cyr_or_other += 1
            continue

        mapped = lemma_map.get(choice_text)
        if not mapped:
            unmapped += 1
            continue

        if mapped == choice_text:
            continue

        updates.append((mapped, choice_id))

    cur.execute("BEGIN")
    cur.executemany(
        "UPDATE vocab_choices SET choice_text = ? WHERE id = ?",
        updates,
    )
    conn.commit()

    post_audit = audit(cur)

    sample_rows = cur.execute(
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
        WHERE vi.is_active = 1
        ORDER BY vi.id, vc.position_index, vc.id
        LIMIT 24
        """
    ).fetchall()

    report = {
        "db_path": str(db_path),
        "backup_path": str(backup_path),
        "pre_audit": pre_audit,
        "post_audit": post_audit,
        "updates_applied": len(updates),
        "unmapped_lat_choices": unmapped,
        "already_cyr_or_other_in_incorrect_choices": already_cyr_or_other,
        "sample_rows": [dict(r) for r in sample_rows],
    }

    conn.close()
    return report


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: fix_vocab_choices_to_russian_multi_db.py <db_path> [<db_path> ...]")

    out = []
    for db in sys.argv[1:]:
        out.append(process_db(db))

    report_path = Path("tmp/fix_vocab_choices_to_russian_multi_db_report.json")
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
