from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block import repo
from services.community_block import ai_repo
from services.community_block.ai_planner import plan_and_persist


def resolve_post_log_id(conn: sqlite3.Connection, post_log_id: int | None, chat_key: str | None) -> int:
    if post_log_id is not None:
        return post_log_id
    if not chat_key:
        raise RuntimeError("either --post-log-id or --chat-key is required")
    resolved = ai_repo.fetch_latest_post_log_id_for_chat(conn, chat_key=chat_key)
    if resolved is None:
        raise RuntimeError(f"no post_log rows for chat_key={chat_key}")
    return resolved


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--post-log-id", type=int, default=None)
    ap.add_argument("--chat-key", default=None)
    ap.add_argument("--min-user-replies", type=int, default=1)
    ap.add_argument("--max-plans-per-thread", type=int, default=2)
    args = ap.parse_args()

    db_path = str(args.db or get_settings().db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        bootstrap_community_layer(conn)
        post_log_id = resolve_post_log_id(conn, args.post_log_id, args.chat_key)
        result = plan_and_persist(
            conn,
            post_log_id=post_log_id,
            min_user_replies=args.min_user_replies,
            max_plans_per_thread=args.max_plans_per_thread,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
