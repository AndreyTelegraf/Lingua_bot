from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path


ALLOWED_ACTIONS = {"keep", "rewrite_light"}


def load_schema(db_path: Path, table: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [dict(r) for r in rows]


def load_review_rows(tsv_path: Path) -> list[dict]:
    with tsv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [dict(row) for row in reader]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--table", default="community_content_items")
    parser.add_argument("--review-tsv", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    schema = load_schema(args.db, args.table)
    colnames = [c["name"] for c in schema]
    rows = load_review_rows(args.review_tsv)

    accepted = []
    rejected = []

    for row in rows:
        action = (row.get("review_action") or "").strip()
        if action not in ALLOWED_ACTIONS:
            rejected.append({"reason": "action_not_allowed", "row": row})
            continue

        preview = {
            "topic": row.get("topic", "").strip(),
            "format_type": row.get("format_type", "").strip(),
            "text": row.get("text", "").strip(),
            "source_scenario_id": row.get("scenario_id", "").strip(),
            "opening_family": row.get("opening_family", "").strip(),
            "source_context": row.get("context", "").strip(),
            "source_intent": row.get("intent", "").strip(),
            "review_action": action,
            "review_note": row.get("review_note", "").strip(),
        }
        accepted.append(preview)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    preview_json = args.out_dir / "community_import_preview_v1.json"
    summary_json = args.out_dir / "community_import_preview_summary_v1.json"

    payload = {
        "table": args.table,
        "schema_columns": colnames,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "accepted": accepted,
        "rejected": rejected[:25],
    }
    preview_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "table": args.table,
        "schema_columns": colnames,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "first_accepted": accepted[:3],
        "first_rejected": rejected[:3],
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
