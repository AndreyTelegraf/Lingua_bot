from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path


def structural_checks(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "active_zero_choices": conn.execute("""
            select count(*) from vocab_items vi
            where vi.is_active=1
              and not exists (
                select 1 from vocab_choices vic where vic.item_id=vi.id
              )
        """).fetchone()[0],
        "active_not_6_choices": conn.execute("""
            select count(*) from (
              select vi.id, count(vic.id) c
              from vocab_items vi
              left join vocab_choices vic on vic.item_id=vi.id
              where vi.is_active=1
              group by vi.id
              having c != 6
            )
        """).fetchone()[0],
        "active_not_1_correct": conn.execute("""
            select count(*) from (
              select vi.id, sum(case when vic.is_correct=1 then 1 else 0 end) c
              from vocab_items vi
              left join vocab_choices vic on vic.item_id=vi.id
              where vi.is_active=1
              group by vi.id
              having c != 1
            )
        """).fetchone()[0],
        "active_not_6_distinct_choices": conn.execute("""
            select count(*) from (
              select vi.id, count(distinct vic.choice_text) c
              from vocab_items vi
              left join vocab_choices vic on vic.item_id=vi.id
              where vi.is_active=1
              group by vi.id
              having c != 6
            )
        """).fetchone()[0],
        "duplicate_active_lemma_pos_count": conn.execute("""
            select count(*) from (
              select lemma, pos, count(*) c
              from vocab_items
              where is_active=1
              group by lemma, pos
              having c > 1
            )
        """).fetchone()[0],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--artifacts-dir", default="artifacts")
    ap.add_argument("--apply-auto-rejects", action="store_true")
    args = ap.parse_args()

    reject_csv = Path(args.artifacts_dir) / "noun_ru_gloss_reject_auto.csv"
    if not reject_csv.exists():
        raise SystemExit(f"reject file not found: {reject_csv}")

    ids: list[int] = []
    with reject_csv.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ids.append(int(row["id"]))

    conn = sqlite3.connect(args.db)
    before = structural_checks(conn)

    deactivated_count = 0
    if args.apply_auto_rejects and ids:
        conn.executemany(
            "update vocab_items set is_active=0 where id=? and is_active=1",
            [(i,) for i in ids],
        )
        deactivated_count = conn.total_changes
        conn.commit()

    after = structural_checks(conn)
    remaining_review_count = 0
    review_csv = Path(args.artifacts_dir) / "noun_ru_gloss_review.csv"
    if review_csv.exists():
        with review_csv.open("r", encoding="utf-8", newline="") as f:
            remaining_review_count = max(sum(1 for _ in f) - 1, 0)

    payload = {
        "apply_auto_rejects": bool(args.apply_auto_rejects),
        "deactivated_count": deactivated_count,
        "remaining_review_count": remaining_review_count,
        "structural_checks_before": before,
        "structural_checks_after": after,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
