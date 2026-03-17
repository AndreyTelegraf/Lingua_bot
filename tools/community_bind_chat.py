from __future__ import annotations

import argparse
import sqlite3

from app.config import get_settings
from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block import repo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-key", required=True)
    parser.add_argument("--real-chat-id", required=True, type=int)
    parser.add_argument("--has-topics", action="store_true")
    parser.add_argument("--default-topic-id", type=int, default=None)
    parser.add_argument("--enable-only", action="store_true")
    args = parser.parse_args()

    db_path = get_settings().db_path
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        bootstrap_community_layer(conn)
        repo.bind_chat_identity(
            conn,
            chat_key=args.chat_key,
            real_chat_id=args.real_chat_id,
            has_topics=args.has_topics,
            default_topic_id=args.default_topic_id,
        )
        if args.enable_only:
            repo.enable_only_chat(conn, chat_key=args.chat_key)
        conn.commit()

        row = repo.get_chat_by_key(conn, chat_key=args.chat_key)
        print("bound_chat=", dict(row) if row else None)
        print("enabled_chats=", [x["chat_key"] for x in repo.list_enabled_chats(conn)])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
