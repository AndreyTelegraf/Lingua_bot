from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from services.vocab_bank.normalize import normalize_raw_entries_to_candidates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--source-name")
    parser.add_argument("--truncate-source", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"db_not_found:{db_path}")

    conn = sqlite3.connect(db_path)
    try:
        inserted = normalize_raw_entries_to_candidates(
            conn,
            source_name=args.source_name,
            truncate_source=args.truncate_source,
        )
    finally:
        conn.close()

    print(f"normalized={inserted}")


if __name__ == "__main__":
    main()
