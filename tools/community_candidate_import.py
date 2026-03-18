#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block.content_registry import import_candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    db_path = Path(settings.db_path)
    input_path = Path(args.file)

    items: list[dict] = []
    with input_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    bootstrap_community_layer(conn)

    result = import_candidates(conn, items=items)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    conn.close()


if __name__ == "__main__":
    main()
