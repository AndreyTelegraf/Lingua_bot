from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from services.community_block import repo
from services.community_block.bootstrap import bootstrap_community_layer


def parse_boolish(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "on", "yes"}:
        return "1"
    if normalized in {"0", "false", "off", "no"}:
        return "0"
    raise SystemExit(f"unsupported value: {value}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--value", required=True)
    args = parser.parse_args()

    conn = sqlite3.connect(get_settings().db_path)
    conn.row_factory = sqlite3.Row
    try:
        bootstrap_community_layer(conn)
        repo.set_runtime_flag(conn, key="dry_run_override", value=parse_boolish(args.value))
        conn.commit()
        print("dry_run_override=", repo.get_runtime_flag(conn, key="dry_run_override"))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
