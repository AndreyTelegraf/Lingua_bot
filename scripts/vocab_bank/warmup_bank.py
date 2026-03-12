from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from services.vocab_bank.warmup import (
    persist_warmup_validation_summary,
    run_warmup_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--topic-tag-prefix")
    parser.add_argument("--build-code", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"db_not_found:{db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        report = run_warmup_report(
            conn,
            topic_tag_prefix=args.topic_tag_prefix,
        )
        persist_warmup_validation_summary(
            conn,
            build_code=args.build_code,
            report=report,
        )
    finally:
        conn.close()

    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
