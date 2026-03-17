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

DBS = [
    Path("data/lingua.db"),
    Path("data/lingua_staging.db"),
]

KEEP_LEMMAS = {
    "proibir",
    "orar",
    "chupar",
    "pisar",
    "saltar",
    "acusar",
    "obedecer",
    "insistir",
}

REPORT_PATH = Path("tmp/align_20k_verbs_to_canonical_core_report.json")
BACKUP_DIR = Path("tmp/db_backups")


def fetch_20k_verbs(cur: sqlite3.Cursor) -> list[dict]:
    rows = cur.execute(
        """
        SELECT
          vi.id,
          vi.lemma,
          vi.correct_answer,
          vi.freq_rank,
          vi.is_active,
          COUNT(vc.id) AS choice_count,
          SUM(CASE WHEN COALESCE(vc.is_correct, 0) = 1 THEN 1 ELSE 0 END) AS correct_count
        FROM vocab_items vi
        LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
        WHERE vi.pos = 'verb'
          AND vi.bin_name = '20K'
          AND vi.freq_rank IS NOT NULL
        GROUP BY vi.id, vi.lemma, vi.correct_answer, vi.freq_rank, vi.is_active
        ORDER BY vi.freq_rank DESC, vi.lemma ASC, vi.id ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    all_reports = []

    for db_path in DBS:
        if not db_path.exists():
            raise SystemExit(f"DB not found: {db_path}")

        backup_path = BACKUP_DIR / f"{db_path.stem}_before_align_20k_verbs_core_{ts}.db"
        shutil.copy2(db_path, backup_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        before = fetch_20k_verbs(cur)

        cur.execute("BEGIN")
        cur.execute(
            """
            UPDATE vocab_items
            SET is_active = 0
            WHERE pos = 'verb'
              AND bin_name = '20K'
            """
        )

        kept_ids = []
        skipped_keep_candidates = []

        rows = cur.execute(
            """
            SELECT
              vi.id,
              vi.lemma,
              COUNT(vc.id) AS choice_count,
              SUM(CASE WHEN COALESCE(vc.is_correct, 0) = 1 THEN 1 ELSE 0 END) AS correct_count
            FROM vocab_items vi
            LEFT JOIN vocab_choices vc ON vc.item_id = vi.id
            WHERE vi.pos = 'verb'
              AND vi.bin_name = '20K'
              AND LOWER(TRIM(vi.lemma)) IN ({})
            GROUP BY vi.id, vi.lemma
            ORDER BY vi.id ASC
            """.format(",".join("?" for _ in KEEP_LEMMAS)),
            tuple(sorted(KEEP_LEMMAS)),
        ).fetchall()

        for row in rows:
            lemma = str(row["lemma"]).strip().lower()
            choice_count = int(row["choice_count"] or 0)
            correct_count = int(row["correct_count"] or 0)
            if lemma in KEEP_LEMMAS and choice_count == 6 and correct_count == 1:
                cur.execute("UPDATE vocab_items SET is_active = 1 WHERE id = ?", (int(row["id"]),))
                kept_ids.append(int(row["id"]))
            else:
                skipped_keep_candidates.append(
                    {
                        "id": int(row["id"]),
                        "lemma": row["lemma"],
                        "choice_count": choice_count,
                        "correct_count": correct_count,
                    }
                )

        conn.commit()

        after = fetch_20k_verbs(cur)

        all_reports.append(
            {
                "db_path": str(db_path),
                "backup_path": str(backup_path),
                "before_active_ids": [int(r["id"]) for r in before if int(r["is_active"] or 0) == 1],
                "after_active_ids": [int(r["id"]) for r in after if int(r["is_active"] or 0) == 1],
                "before_active_lemmas": [r["lemma"] for r in before if int(r["is_active"] or 0) == 1],
                "after_active_lemmas": [r["lemma"] for r in after if int(r["is_active"] or 0) == 1],
                "kept_ids": kept_ids,
                "skipped_keep_candidates": skipped_keep_candidates,
                "before": before,
                "after": after,
            }
        )

        conn.close()

    REPORT_PATH.write_text(json.dumps(all_reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(all_reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
