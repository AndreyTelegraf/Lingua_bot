#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

if os.environ.get("LINGUABOT_ALLOW_UNSAFE_DIRECT_ACTIVATION") != "1":
    raise SystemExit(
        "Blocked: this legacy script performs direct vocab_items.is_active=1 writes and bypasses the strict activation gate in services/vocab_bank/validate_items.py. "
        "Use the canonical publish path instead. "
        "Override only for forensic/manual recovery with LINGUABOT_ALLOW_UNSAFE_DIRECT_ACTIVATION=1."
    )


import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/lingua_staging.db")
BACKUP_DIR = Path("tmp/db_backups")
REPORT_PATH = Path("tmp/promote_5k_adverbs_safe_set_staging_report.json")

PROMOTE_IDS = [3972, 3971, 3400]  # cuidadosamente, dificilmente, sozinho


def fetch_rows(cur: sqlite3.Cursor, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    rows = cur.execute(
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
        WHERE vi.id IN ({",".join("?" for _ in ids)})
        GROUP BY vi.id, vi.lemma, vi.correct_answer, vi.pos, vi.bin_name, vi.freq_rank, vi.is_active, vi.topic_tag
        ORDER BY vi.freq_rank DESC, vi.id ASC
        """,
        tuple(ids),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_5k_adverb_summary(cur: sqlite3.Cursor) -> dict:
    rows = cur.execute(
        """
        SELECT
          vi.id,
          vi.lemma,
          vi.is_active,
          COUNT(vc.id) AS choice_count,
          SUM(CASE WHEN COALESCE(vc.is_correct, 0) = 1 THEN 1 ELSE 0 END) AS correct_count
        FROM vocab_items vi
        LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.pos = 'adverb'
          AND vi.bin_name = '5K'
          AND vi.freq_rank IS NOT NULL
        GROUP BY vi.id, vi.lemma, vi.is_active
        """
    ).fetchall()

    rows = [dict(r) for r in rows]
    return {
        "total_rows": len(rows),
        "active_rows": sum(1 for r in rows if int(r["is_active"] or 0) == 1),
        "valid_6_1_rows": sum(
            1
            for r in rows
            if int(r["choice_count"] or 0) == 6 and int(r["correct_count"] or 0) == 1
        ),
        "active_lemmas": sorted(
            r["lemma"] for r in rows if int(r["is_active"] or 0) == 1
        ),
    }


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"{DB_PATH.stem}_before_promote_5k_adverbs_safe_set_{ts}.db"
    shutil.copy2(DB_PATH, backup_path)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    before_rows = fetch_rows(cur, PROMOTE_IDS)
    before_summary = fetch_5k_adverb_summary(cur)

    bad_candidates = [
        r for r in before_rows
        if not (
            r["pos"] == "adverb"
            and r["bin_name"] == "5K"
            and int(r["choice_count"] or 0) == 6
            and int(r["correct_count"] or 0) == 1
        )
    ]
    if bad_candidates:
        raise SystemExit(
            "Refusing to promote invalid candidates:\n"
            + json.dumps(bad_candidates, ensure_ascii=False, indent=2)
        )

    cur.execute("BEGIN")
    cur.execute(
        f"UPDATE vocab_items SET is_active = 1 WHERE id IN ({','.join('?' for _ in PROMOTE_IDS)})",
        tuple(PROMOTE_IDS),
    )
    conn.commit()

    after_rows = fetch_rows(cur, PROMOTE_IDS)
    after_summary = fetch_5k_adverb_summary(cur)

    report = {
        "db_path": str(DB_PATH),
        "backup_path": str(backup_path),
        "promote_ids": PROMOTE_IDS,
        "before_rows": before_rows,
        "after_rows": after_rows,
        "before_summary": before_summary,
        "after_summary": after_summary,
    }

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
