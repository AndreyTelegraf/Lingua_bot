from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import subprocess
from pathlib import Path

from services.vocab_qa.router import (
    available_positions,
    count_key,
    get_audit_runner,
    reject_csv_name,
    review_csv_name,
)


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
        "active_noun": conn.execute("select count(*) from vocab_items where is_active=1 and pos='noun'").fetchone()[0],
        "active_verb": conn.execute("select count(*) from vocab_items where is_active=1 and pos='verb'").fetchone()[0],
        "active_adjective": conn.execute("select count(*) from vocab_items where is_active=1 and pos='adjective'").fetchone()[0],
        "active_adverb": conn.execute("select count(*) from vocab_items where is_active=1 and pos='adverb'").fetchone()[0],
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


def resolve_positions(raw_pos: str) -> list[str]:
    if raw_pos == "all":
        return list(available_positions())
    if raw_pos not in available_positions():
        raise ValueError(f"Unsupported --pos: {raw_pos}")
    return [raw_pos]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--artifacts-dir", default="artifacts")
    ap.add_argument("--pos", default="all")
    ap.add_argument("--ingest-cmd", default="")
    ap.add_argument("--apply-auto-rejects", action="store_true")
    ap.add_argument("--review-threshold", type=int, default=25)
    ap.add_argument("--reject-threshold", type=int, default=50)
    ap.add_argument("--allow-review-tail", action="store_true")
    args = ap.parse_args()

    positions = resolve_positions(args.pos)
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
            "positions": positions,
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
                "positions": positions,
                "ingest_cmd": args.ingest_cmd,
                "ingest_rc": ingest_rc,
            }
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 3

    pos_results: dict[str, dict] = {}
    total_reject_count = 0
    total_review_count = 0
    total_deactivated_count = 0
    decision = "GO"
    reasons: list[str] = []

    for pos in positions:
        audit_runner = get_audit_runner(pos)
        audit_summary = audit_runner(args.db, str(artifacts_dir))

        reject_csv = artifacts_dir / reject_csv_name(pos)
        review_csv = artifacts_dir / review_csv_name(pos)

        reject_ids = load_reject_ids(reject_csv)
        review_count = count_review_rows(review_csv)
        reject_count = len(reject_ids)

        pos_decision = "GO"
        pos_reasons: list[str] = []

        if reject_count > args.reject_threshold:
            pos_decision = "HOLD"
            pos_reasons.append("reject_threshold_exceeded")

        if review_count > args.review_threshold and not args.allow_review_tail:
            pos_decision = "HOLD"
            pos_reasons.append("review_threshold_exceeded")

        deactivated_count = 0
        if pos_decision != "HOLD" and args.apply_auto_rejects:
            deactivated_count = apply_auto_rejects(args.db, reject_ids)

        if pos_decision == "GO" and review_count > 0:
            pos_decision = "SOFT_GO"

        pos_results[pos] = {
            "decision": pos_decision,
            "reasons": pos_reasons,
            "audit_summary": audit_summary,
            "reject_count": reject_count,
            "review_count": review_count,
            "deactivated_count": deactivated_count,
        }

        total_reject_count += reject_count
        total_review_count += review_count
        total_deactivated_count += deactivated_count

        if pos_decision == "HOLD":
            decision = "HOLD"
            reasons.append(f"{pos}:hold")
        elif pos_decision == "SOFT_GO" and decision == "GO":
            decision = "SOFT_GO"

    conn = sqlite3.connect(args.db)
    post_checks = structural_checks(conn)
    post_counts = counts_snapshot(conn)
    conn.close()

    if not all_green(post_checks):
        decision = "HOLD"
        reasons.append("post_checks_not_green")

    payload = {
        "decision": decision,
        "reasons": reasons,
        "positions": positions,
        "ingest_cmd": args.ingest_cmd,
        "ingest_rc": ingest_rc,
        "apply_auto_rejects": bool(args.apply_auto_rejects),
        "review_threshold": args.review_threshold,
        "reject_threshold": args.reject_threshold,
        "allow_review_tail": bool(args.allow_review_tail),
        "pre_counts": pre_counts,
        "post_counts": post_counts,
        "pre_checks": pre_checks,
        "post_checks": post_checks,
        "per_pos": pos_results,
        "totals": {
            "reject_count": total_reject_count,
            "review_count": total_review_count,
            "deactivated_count": total_deactivated_count,
        },
        "artifacts_dir": str(artifacts_dir),
    }

    out = artifacts_dir / "pos_semi_auto_pipeline_summary.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if decision in {"GO", "SOFT_GO"} else 4


if __name__ == "__main__":
    raise SystemExit(main())
