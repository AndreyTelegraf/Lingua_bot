from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import subprocess
from pathlib import Path

from services.vocab_qa.adjective_gloss_audit import run_adjective_audit


def structural_checks(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "active_zero_choices": conn.execute("""
            select count(*) from vocab_items vi
            where vi.is_active=1
              and not exists (
                select 1 from vocab_choices vc where vc.item_id=vi.id
              )
        """).fetchone()[0],
        "active_not_6_choices": conn.execute("""
            select count(*) from (
              select vi.id, count(vc.id) c
              from vocab_items vi
              left join vocab_choices vc on vc.item_id=vi.id
              where vi.is_active=1
              group by vi.id
              having c != 6
            )
        """).fetchone()[0],
        "active_not_1_correct": conn.execute("""
            select count(*) from (
              select vi.id, sum(case when vc.is_correct=1 then 1 else 0 end) c
              from vocab_items vi
              left join vocab_choices vc on vc.item_id=vi.id
              where vi.is_active=1
              group by vi.id
              having c != 1
            )
        """).fetchone()[0],
        "active_not_6_distinct_choices": conn.execute("""
            select count(*) from (
              select vi.id, count(distinct vc.choice_text) c
              from vocab_items vi
              left join vocab_choices vc on vc.item_id=vi.id
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


def all_green(checks: dict[str, int]) -> bool:
    return all(v == 0 for v in checks.values())


def counts_snapshot(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "active_total": conn.execute("select count(*) from vocab_items where is_active=1").fetchone()[0],
        "active_adjective": conn.execute("select count(*) from vocab_items where is_active=1 and pos='adjective'").fetchone()[0],
    }


def load_reject_ids(path: Path) -> list[int]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return [int(row["id"]) for row in csv.DictReader(f)]


def count_review_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as f:
        return max(sum(1 for _ in f) - 1, 0)


def apply_auto_rejects(db_path: str, reject_ids: list[int]) -> int:
    if not reject_ids:
        return 0
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "update vocab_items set is_active=0 where id=? and is_active=1",
        [(i,) for i in reject_ids],
    )
    changed = conn.total_changes
    conn.commit()
    conn.close()
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--artifacts-dir", default="artifacts")
    ap.add_argument("--ingest-cmd", default="")
    ap.add_argument("--apply-auto-rejects", action="store_true")
    ap.add_argument("--review-threshold", type=int, default=25)
    ap.add_argument("--reject-threshold", type=int, default=50)
    ap.add_argument("--allow-review-tail", action="store_true")
    args = ap.parse_args()

    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    pre_checks = structural_checks(conn)
    pre_counts = counts_snapshot(conn)
    conn.close()

    if not all_green(pre_checks):
        payload = {
            "decision": "HOLD",
            "reason": "pre_checks_not_green",
            "pre_checks": pre_checks,
            "pre_counts": pre_counts,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 2

    ingest_rc = None
    if args.ingest_cmd.strip():
        run = subprocess.run(args.ingest_cmd, shell=True)
        ingest_rc = run.returncode
        if ingest_rc != 0:
            payload = {
                "decision": "HOLD",
                "reason": "ingest_cmd_failed",
                "ingest_cmd": args.ingest_cmd,
                "ingest_rc": ingest_rc,
            }
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 3

    audit_summary = run_adjective_audit(args.db, str(artifacts_dir))
    reject_csv = artifacts_dir / "adjective_ru_gloss_reject_auto.csv"
    review_csv = artifacts_dir / "adjective_ru_gloss_review.csv"

    reject_ids = load_reject_ids(reject_csv)
    review_count = count_review_rows(review_csv)
    reject_count = len(reject_ids)

    decision = "GO"
    reasons: list[str] = []

    if reject_count > args.reject_threshold:
        decision = "HOLD"
        reasons.append("reject_threshold_exceeded")

    if review_count > args.review_threshold and not args.allow_review_tail:
        decision = "HOLD"
        reasons.append("review_threshold_exceeded")

    deactivated_count = 0
    if decision != "HOLD" and args.apply_auto_rejects:
        deactivated_count = apply_auto_rejects(args.db, reject_ids)

    conn = sqlite3.connect(args.db)
    post_checks = structural_checks(conn)
    post_counts = counts_snapshot(conn)
    conn.close()

    if not all_green(post_checks):
        decision = "HOLD"
        reasons.append("post_checks_not_green")

    if decision == "GO" and review_count > 0:
        decision = "SOFT_GO"

    payload = {
        "decision": decision,
        "reasons": reasons,
        "ingest_cmd": args.ingest_cmd,
        "ingest_rc": ingest_rc,
        "apply_auto_rejects": bool(args.apply_auto_rejects),
        "pre_counts": pre_counts,
        "post_counts": post_counts,
        "pre_checks": pre_checks,
        "post_checks": post_checks,
        "audit_summary": audit_summary,
        "reject_count": reject_count,
        "review_count": review_count,
        "deactivated_count": deactivated_count,
        "artifacts_dir": str(artifacts_dir),
    }

    out = artifacts_dir / "adjective_semi_auto_pipeline_summary.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if decision in {"GO", "SOFT_GO"} else 4


if __name__ == "__main__":
    raise SystemExit(main())
