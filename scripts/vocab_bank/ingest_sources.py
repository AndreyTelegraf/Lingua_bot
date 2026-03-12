from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from services.vocab_bank.ingest import ingest_entries, load_entries


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--format", required=True, choices=["csv", "jsonl"])
    parser.add_argument("--truncate-source", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    db_path = Path(args.db)
    input_path = Path(args.input)

    if not db_path.exists():
        raise SystemExit(f"db_not_found:{db_path}")
    if not input_path.exists():
        raise SystemExit(f"input_not_found:{input_path}")

    entries = load_entries(
        input_path,
        source_name=args.source_name,
        file_format=args.format,
    )

    conn = sqlite3.connect(db_path)
    try:
        inserted = ingest_entries(
            conn,
            entries=entries,
            truncate_source=args.truncate_source,
        )
    finally:
        conn.close()

    print(f"inserted={inserted}")


if __name__ == "__main__":
    main()
