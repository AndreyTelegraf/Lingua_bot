from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path

VALID_DECISIONS = {"keep", "deactivate", "fix_correct_answer", ""}

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

def apply_fix(conn: sqlite3.Connection, item_id: int, replacement: str) -> dict:
    replacement = (replacement or "").strip()
    if not replacement:
        raise ValueError(f"replacement_correct_answer is empty for item_id={item_id}")

    item = conn.execute(
        "select id, correct_answer from vocab_items where id=?",
        (item_id,),
    ).fetchone()
    if not item:
        raise ValueError(f"item not found: {item_id}")

    choices = conn.execute(
        "select id, choice_text, is_correct from vocab_choices where item_id=? order by position_index",
        (item_id,),
    ).fetchall()

    matched_choice_id = None
    for ch in choices:
        if (ch[1] or "").strip() == replacement:
            matched_choice_id = ch[0]
            break

    if matched_choice_id is None:
        raise ValueError(f"replacement choice not found for item_id={item_id}: {replacement}")

    conn.execute(
        "update vocab_items set correct_answer=? where id=?",
        (replacement, item_id),
    )
    conn.execute(
        "update vocab_choices set is_correct=0 where item_id=?",
        (item_id,),
    )
    conn.execute(
        "update vocab_choices set is_correct=1 where id=?",
        (matched_choice_id,),
    )

    return {
        "item_id": item_id,
        "old_correct_answer": item[1],
        "new_correct_answer": replacement,
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument(
        "--sheet",
        default="artifacts/unified_manual_review_decision_sheet.csv",
    )
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    sheet = Path(args.sheet)
    if not sheet.exists():
        raise SystemExit(f"decision sheet not found: {sheet}")

    with sheet.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    conn = sqlite3.connect(args.db)
    before = structural_checks(conn)

    stats = {
        "rows_total": len(rows),
        "keep_count": 0,
        "deactivate_count": 0,
        "fix_count": 0,
        "skipped_empty_decision": 0,
    }
    applied = []

    for row in rows:
        decision = (row.get("decision") or "").strip()
        if decision not in VALID_DECISIONS:
            raise ValueError(f"invalid decision for id={row.get('id')}: {decision}")

        if decision == "":
            stats["skipped_empty_decision"] += 1
            continue

        item_id = int(row["id"])

        if decision == "keep":
            stats["keep_count"] += 1
            applied.append({"id": item_id, "decision": "keep"})
            continue

        if not args.apply:
            if decision == "deactivate":
                stats["deactivate_count"] += 1
            elif decision == "fix_correct_answer":
                stats["fix_count"] += 1
            applied.append({"id": item_id, "decision": decision})
            continue

        if decision == "deactivate":
            conn.execute(
                "update vocab_items set is_active=0 where id=? and is_active=1",
                (item_id,),
            )
            stats["deactivate_count"] += 1
            applied.append({"id": item_id, "decision": "deactivate"})
        elif decision == "fix_correct_answer":
            payload = apply_fix(conn, item_id, row.get("replacement_correct_answer") or "")
            stats["fix_count"] += 1
            applied.append({"id": item_id, "decision": "fix_correct_answer", **payload})
        elif decision == "keep":
            stats["keep_count"] += 1
            applied.append({"id": item_id, "decision": "keep"})

    if args.apply:
        conn.commit()

    after = structural_checks(conn)
    conn.close()

    payload = {
        "apply": bool(args.apply),
        "stats": stats,
        "structural_checks_before": before,
        "structural_checks_after": after,
        "applied_preview": applied[:20],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
