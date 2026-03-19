from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys
from pathlib import Path

from aiogram import Bot

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block.decision import choose_post_candidate
from services.community_block import repo
from services.community_block.sender import send_post


def load_env_file(path: str | None) -> None:
    if not path:
        return
    env_path = Path(path)
    if not env_path.exists():
        raise RuntimeError(f"env file not found: {env_path}")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ[k.strip()] = v.strip()


def resolve_db_path(explicit_db: str | None, settings) -> str:
    return explicit_db or str(settings.db_path)


async def amain() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-key", required=True)
    parser.add_argument("--content-id", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db", default=None)
    parser.add_argument("--env-file", default=None)
    args = parser.parse_args()

    load_env_file(args.env_file)
    settings = get_settings()
    db_path = resolve_db_path(args.db, settings)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        bootstrap_community_layer(conn)

        chat = repo.get_chat_by_key(conn, chat_key=args.chat_key)
        if chat is None:
            raise RuntimeError(f"unknown chat_key: {args.chat_key}")

        if args.content_id is not None:
            content = repo.get_content_item(conn, content_id=args.content_id)
            if content is None:
                raise RuntimeError(f"unknown content_id: {args.content_id}")
            decision_allowed = bool(chat["is_enabled"])
            text = str(content["text"])
            content_id = int(content["id"])
        else:
            decision = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=args.dry_run)
            print("decision=", decision)
            if not decision.allowed:
                raise RuntimeError(f"posting blocked: {decision.reason}")
            content = repo.get_content_item(conn, content_id=int(decision.content_id))
            if content is None:
                raise RuntimeError("chosen content not found")
            decision_allowed = True
            text = str(content["text"])
            content_id = int(content["id"])

        if not decision_allowed:
            raise RuntimeError("chat is not enabled")

        if args.dry_run:
            print("dry_run_chat=", dict(chat))
            print("dry_run_content=", dict(content))
            return

        bot = Bot(token=settings.bot_token)
        try:
            message_id = await send_post(
                bot,
                chat_id=int(chat["chat_id"]),
                text=text,
                default_topic_id=chat["default_topic_id"],
            )
        finally:
            await bot.session.close()

        post_log_id = repo.log_post(
            conn,
            chat_id=int(chat["chat_id"]),
            content_id=content_id,
            thread_root_message_id=message_id,
            posted_message_id=message_id,
        )
        conn.commit()

        print("posted_message_id=", message_id)
        print("post_log_id=", post_log_id)
    finally:
        conn.close()


if __name__ == "__main__":
    asyncio.run(amain())
