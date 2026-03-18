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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-key", required=True)
    parser.add_argument("--time", required=True)
    args = parser.parse_args()

    conn = sqlite3.connect(get_settings().db_path)
    conn.row_factory = sqlite3.Row
    try:
        bootstrap_community_layer(conn)
        repo.set_chat_daily_post_time(conn, chat_key=args.chat_key, daily_post_time=args.time)
        conn.commit()
        row = repo.get_chat_by_key(conn, chat_key=args.chat_key)
        print("chat=", dict(row) if row else None)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
