from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from services.vocab_bank.validate_items import validate_and_publish_items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--topic-tag-prefix")
    parser.add_argument("--build-code", required=True)
    parser.add_argument("--no-publish", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"db_not_found:{db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        published = validate_and_publish_items(
            conn,
            topic_tag_prefix=args.topic_tag_prefix,
            build_code=args.build_code,
            publish=not args.no_publish,
        )
    finally:
        conn.close()

    print(f"published={published}")


if __name__ == "__main__":
    main()
