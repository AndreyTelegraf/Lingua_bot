#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/lingua.db")
BACKUP_DIR = Path("tmp/db_backups")
REPORT_PATH = Path("tmp/fix_vocab_choices_to_russian_report.json")


def classify_text(s: str | None) -> str:
    s = (s or "").strip()
    if not s:
        return "EMPTY"
    has_cyr = any("А" <= ch <= "я" or ch in "Ёё" for ch in s)
    has_lat = any(("A" <= ch <= "Z") or ("a" <= ch <= "z") or ch in "ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ" for ch in s)
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
        SELECT lemma, correct_answer, COUNT(*) AS cnt
        FROM vocab_items
        GROUP BY lemma, correct_answer
        """
    ).fetchall()

    grouped: dict[str, set[str]] = {}
    for lemma, correct_answer, _cnt in rows:
        grouped.setdefault(lemma, set()).add(correct_answer)

    return {lemma: list(vals)[0] for lemma, vals in grouped.items() if len(vals) == 1}


def audit(cur: sqlite3.Cursor) -> dict:
    rows = cur.execute(
        """
        SELECT
          vi.id,
          vi.lemma,
          vi.correct_answer,
          vc.choice_text,
          vc.is_correct
        FROM vocab_items vi
        JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.is_active = 1
        ORDER BY vi.id, vc.position_index, vc.id
        """
    ).fetchall()

    by_item: dict[int, dict] = {}
    for item_id, lemma, correct_answer, choice_text, is_correct in rows:
        entry = by_item.setdefault(
            item_id,
            {
                "lemma": lemma,
                "correct_answer": correct_answer,
                "correct_class": classify_text(correct_answer),
                "bad_distractors": 0,
                "choices": 0,
            },
        )
        entry["choices"] += 1
        if is_correct != 1 and entry["correct_class"] == "CYR" and classify_text(choice_text) in {"LAT", "MIXED"}:
            entry["bad_distractors"] += 1

    items_with_bad = sum(1 for x in by_item.values() if x["bad_distractors"] > 0)
    total_bad = sum(x["bad_distractors"] for x in by_item.values())
    return {
        "active_items_seen": len(by_item),
        "items_with_lat_distractor_when_answer_cyr": items_with_bad,
        "total_bad_distractors": total_bad,
    }


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"lingua_before_choice_fix_{ts}.db"
    shutil.copy2(DB_PATH, backup_path)

    conn = sqlite3.connect(DB_PATH)
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
        LIMIT 60
        """
    ).fetchall()

    report = {
        "backup_path": str(backup_path),
        "pre_audit": pre_audit,
        "post_audit": post_audit,
        "updates_applied": len(updates),
        "unmapped_lat_choices": unmapped,
        "already_cyr_or_other_in_incorrect_choices": already_cyr_or_other,
        "sample_rows": [dict(r) for r in sample_rows],
    }

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
