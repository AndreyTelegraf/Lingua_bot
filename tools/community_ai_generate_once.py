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
from services.community_block import ai_repo, repo
from services.community_block.ai_planner import plan_and_persist
from services.community_block.ai_generator import generate_from_prompt_payload


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
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    db_path = str(args.db or get_settings().db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        bootstrap_community_layer(conn)
        post_log_id = resolve_post_log_id(conn, args.post_log_id, args.chat_key)
        plan = plan_and_persist(
            conn,
            post_log_id=post_log_id,
            min_user_replies=args.min_user_replies,
            max_plans_per_thread=args.max_plans_per_thread,
        )

        if not plan["decision"]["should_reply"]:
            print(json.dumps({
                "status": "planned_no_reply",
                "plan": plan,
            }, ensure_ascii=False, indent=2))
            return

        generated = generate_from_prompt_payload(plan["prompt_payload"], model=args.model)
        print(json.dumps({
            "status": "generated",
            "plan": plan,
            "generated": {
                "provider": generated.provider,
                "model": generated.model,
                "response_id": generated.response_id,
                "text": generated.text,
                "raw": generated.raw,
            },
        }, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
