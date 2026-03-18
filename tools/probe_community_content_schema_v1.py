from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--table", default="community_content_items")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    if not table_exists(conn, args.table):
        raise SystemExit(f"table not found: {args.table}")

    cols = []
    for row in conn.execute(f"PRAGMA table_info({args.table})").fetchall():
        cols.append(
            {
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"],
                "notnull": row["notnull"],
                "default": row["dflt_value"],
                "pk": row["pk"],
            }
        )

    sample_rows = []
    try:
        rows = conn.execute(f"SELECT * FROM {args.table} LIMIT 3").fetchall()
        for row in rows:
            sample_rows.append(dict(row))
    except Exception as e:
        sample_rows = [{"error": str(e)}]

    payload = {
        "db": str(args.db),
        "table": args.table,
        "columns": cols,
        "sample_rows": sample_rows,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
