from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from services.vocab_bank.build_items import build_vocab_items_from_candidates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--source-name")
    parser.add_argument("--truncate-topic-prefix")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"db_not_found:{db_path}")

    conn = sqlite3.connect(db_path)
    try:
        inserted = build_vocab_items_from_candidates(
            conn,
            source_name=args.source_name,
            truncate_topic_prefix=args.truncate_topic_prefix,
        )
    finally:
        conn.close()

    print(f"built_items={inserted}")


if __name__ == "__main__":
    main()
