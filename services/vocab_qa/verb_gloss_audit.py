from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from services.vocab_qa.verb_gloss_rules import evaluate_verb_ru_gloss


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


def run_verb_audit(db_path: str, artifacts_dir: str = "artifacts") -> dict:
    out = Path(artifacts_dir)
    out.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    before = structural_checks(conn)
    rows = conn.execute("""
        select id, lemma, pos
        from vocab_items
        where is_active=1 and pos='verb'
        order by id
    """).fetchall()

    audit_jsonl = out / "verb_ru_gloss_audit.jsonl"
    review_csv = out / "verb_ru_gloss_review.csv"
    reject_csv = out / "verb_ru_gloss_reject_auto.csv"
    summary_json = out / "verb_ru_gloss_summary.json"

    fieldnames = [
        "id", "lemma", "pos", "correct_answer", "status", "risk_score",
        "flags", "normalized_correct_answer", "suggested_action", "explanation"
    ]

    ok_count = 0
    review_count = 0
    reject_count = 0
    auto_reject_count = 0
    top_flags: dict[str, int] = {}

    with audit_jsonl.open("w", encoding="utf-8") as jf, \
         review_csv.open("w", encoding="utf-8", newline="") as rf, \
         reject_csv.open("w", encoding="utf-8", newline="") as af:

        review_writer = csv.DictWriter(rf, fieldnames=fieldnames)
        reject_writer = csv.DictWriter(af, fieldnames=fieldnames)
        review_writer.writeheader()
        reject_writer.writeheader()

        for row in rows:
            correct = conn.execute("""
                select choice_text
                from vocab_choices
                where item_id=? and is_correct=1
            """, (row["id"],)).fetchone()
            gloss = correct[0] if correct else row["lemma"]
            result = evaluate_verb_ru_gloss(lemma=row["lemma"], pos=row["pos"], gloss=gloss)

            payload = {
                "id": row["id"],
                "lemma": row["lemma"],
                "pos": row["pos"],
                "correct_answer": gloss,
                **result.to_dict(),
            }
            jf.write(json.dumps(payload, ensure_ascii=False) + "\n")

            for fl in payload["flags"]:
                top_flags[fl] = top_flags.get(fl, 0) + 1

            if payload["status"] == "ok":
                ok_count += 1
            elif payload["status"] == "review":
                review_count += 1
                review_writer.writerow({**payload, "flags": "|".join(payload["flags"])})
            else:
                reject_count += 1
                auto_reject_count += 1
                reject_writer.writerow({**payload, "flags": "|".join(payload["flags"])})

    after = structural_checks(conn)
    conn.close()

    summary = {
        "scope": "verb_active_only",
        "active_items_scanned": len(rows),
        "ok_count": ok_count,
        "review_count": review_count,
        "reject_count": reject_count,
        "auto_reject_count": auto_reject_count,
        "top_flags": dict(sorted(top_flags.items(), key=lambda kv: (-kv[1], kv[0]))[:20]),
        "structural_checks_before": before,
        "structural_checks_after": after,
    }
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary
