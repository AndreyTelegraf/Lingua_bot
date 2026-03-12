from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from services.vocab_bank.build_choices import build_vocab_choices_for_items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--topic-tag-prefix")
    parser.add_argument("--truncate-existing", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"db_not_found:{db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        built = build_vocab_choices_for_items(
            conn,
            topic_tag_prefix=args.topic_tag_prefix,
            truncate_existing=args.truncate_existing,
        )
    finally:
        conn.close()

    print(f"built_choice_sets={built}")


if __name__ == "__main__":
    main()
