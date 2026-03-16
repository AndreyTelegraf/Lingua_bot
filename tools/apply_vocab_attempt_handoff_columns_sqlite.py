from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    db_path = Path(args.db)
    conn = sqlite3.connect(db_path)

    cols = column_names(conn, "vocab_attempts")
    added: list[str] = []

    if "product_band" not in cols:
        conn.execute("ALTER TABLE vocab_attempts ADD COLUMN product_band TEXT")
        added.append("product_band")
    if "confidence" not in cols:
        conn.execute("ALTER TABLE vocab_attempts ADD COLUMN confidence TEXT")
        added.append("confidence")
    if "result_snapshot_json" not in cols:
        conn.execute("ALTER TABLE vocab_attempts ADD COLUMN result_snapshot_json TEXT")
        added.append("result_snapshot_json")

    conn.commit()
    conn.close()

    print({
        "db": str(db_path),
        "added": added,
    })


if __name__ == "__main__":
    main()
