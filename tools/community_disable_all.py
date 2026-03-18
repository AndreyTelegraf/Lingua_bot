from __future__ import annotations

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
    conn = sqlite3.connect(get_settings().db_path)
    conn.row_factory = sqlite3.Row
    try:
        bootstrap_community_layer(conn)
        changed = repo.disable_all_chats(conn)
        conn.commit()
        print("disabled_count=", changed)
        print("enabled_chats=", [row["chat_key"] for row in repo.list_enabled_chats(conn)])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
