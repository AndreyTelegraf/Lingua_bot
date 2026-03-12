from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from services.vocab_bank.merge import merge_candidates_for_source


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--source-name")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"db_not_found:{db_path}")

    conn = sqlite3.connect(db_path)
    try:
        affected = merge_candidates_for_source(
            conn,
            source_name=args.source_name,
        )
    finally:
        conn.close()

    print(f"merged={affected}")


if __name__ == "__main__":
    main()
