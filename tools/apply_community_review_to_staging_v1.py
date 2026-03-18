from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path


ALLOWED_ACTIONS = {"keep", "rewrite_light"}


@dataclass(slots=True)
class ReviewRow:
    scenario_id: str
    topic: str
    format_type: str
    opening_family: str
    context: str
    intent: str
    review_action: str
    review_note: str
    text: str


def load_review_rows(tsv_path: Path) -> list[ReviewRow]:
    with tsv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        out: list[ReviewRow] = []
        for row in reader:
            out.append(
                ReviewRow(
                    scenario_id=(row.get("scenario_id") or "").strip(),
                    topic=(row.get("topic") or "").strip() or None,
                    format_type=(row.get("format_type") or "").strip(),
                    opening_family=(row.get("opening_family") or "").strip(),
                    context=(row.get("context") or "").strip(),
                    intent=(row.get("intent") or "").strip(),
                    review_action=(row.get("review_action") or "").strip(),
                    review_note=(row.get("review_note") or "").strip(),
                    text=(row.get("text") or "").strip(),
                )
            )
        return out


def backup_db(db_path: Path, backup_path: Path) -> None:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, backup_path)


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def existing_texts(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"SELECT text FROM {table}").fetchall()
    return {row[0] for row in rows}


def insert_row(conn: sqlite3.Connection, table: str, row: ReviewRow) -> int:
    cur = conn.execute(
        f"""
        INSERT INTO {table} (
            text,
            format_type,
            topic,
            region,
            has_question,
            difficulty,
            is_active,
            priority
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.text,
            row.format_type,
            row.topic,
            None,
            1,
            "light",
            1,
            50,
        ),
    )
    return int(cur.lastrowid)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--table", default="community_content_items")
    parser.add_argument("--review-tsv", type=Path, required=True)
    parser.add_argument("--backup-db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    rows = load_review_rows(args.review_tsv)
    accepted = [r for r in rows if r.review_action in ALLOWED_ACTIONS]
    rejected = [r for r in rows if r.review_action not in ALLOWED_ACTIONS]

    conn = sqlite3.connect(args.db)
    cols = table_columns(conn, args.table)

    required = {
        "text",
        "format_type",
        "topic",
        "region",
        "has_question",
        "difficulty",
        "is_active",
        "priority",
    }
    missing = sorted(required - set(cols))
    if missing:
        raise SystemExit(f"missing required columns in {args.table}: {missing}")

    existing = existing_texts(conn, args.table)
    to_insert: list[ReviewRow] = []
    skipped_duplicates: list[dict] = []

    for row in accepted:
        if not row.text or not row.format_type:
            skipped_duplicates.append({"reason": "missing_required_value", "text": row.text})
            continue
        if row.text in existing:
            skipped_duplicates.append({"reason": "duplicate_text", "text": row.text})
            continue
        to_insert.append(row)

    inserted: list[dict] = []

    if args.apply:
        backup_db(args.db, args.backup_db)
        try:
            for row in to_insert:
                new_id = insert_row(conn, args.table, row)
                inserted.append(
                    {
                        "id": new_id,
                        "text": row.text,
                        "topic": row.topic,
                        "format_type": row.format_type,
                        "scenario_id": row.scenario_id,
                    }
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    payload = {
        "db": str(args.db),
        "table": args.table,
        "apply": args.apply,
        "accepted_input_count": len(accepted),
        "rejected_input_count": len(rejected),
        "to_insert_count": len(to_insert),
        "skipped_count": len(skipped_duplicates),
        "inserted_count": len(inserted),
        "backup_db": str(args.backup_db) if args.apply else None,
        "inserted_head": inserted[:10],
        "skipped_head": skipped_duplicates[:10],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
