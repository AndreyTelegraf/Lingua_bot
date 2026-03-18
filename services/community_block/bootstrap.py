from __future__ import annotations

from services.community_block import repo
from services.community_block.models import COMMUNITY_RUNTIME_KEYS
from services.community_block.registry import (
    DEFAULT_CHAT_DEFINITIONS,
    DEFAULT_COMMUNITY_CHAT_KEYS,
)

DEFAULT_CONTENT_ITEMS: tuple[dict[str, object], ...] = (
    {
        "text": "Как бы вы по-португальски мягко сказали продавцу, что цена уже слегка из параллельной вселенной?",
        "format_type": "nuance",
        "topic": "financas",
        "region": None,
        "has_question": True,
        "difficulty": "light",
        "priority": 50,
    },
    {
        "text": "Чем в живой речи чаще заменяют formalíssimo “habitação” когда говорят про съём, квартиру и бытовуху?",
        "format_type": "local",
        "topic": "housing",
        "region": None,
        "has_question": True,
        "difficulty": "light",
        "priority": 50,
    },
    {
        "text": "Как бы вы сказали это по-простому, а не языком уставшего чиновника AIMA?",
        "format_type": "dialogue",
        "topic": "documents",
        "region": None,
        "has_question": True,
        "difficulty": "light",
        "priority": 50,
    },
)

def ensure_runtime_defaults(conn) -> None:
    for key, value in COMMUNITY_RUNTIME_KEYS.items():
        if repo.get_runtime_flag(conn, key=key) is None:
            repo.set_runtime_flag(conn, key=key, value=value)

def ensure_default_chats(conn) -> None:
    seen = set(DEFAULT_COMMUNITY_CHAT_KEYS)
    for row in DEFAULT_CHAT_DEFINITIONS:
        if str(row["chat_key"]) not in seen:
            continue

        existing = repo.get_chat_by_key(conn, chat_key=str(row["chat_key"]))
        if existing is None:
            repo.upsert_chat(conn, **row)
            continue

        conn.execute(
            """
            UPDATE community_chats
            SET chat_id = ?,
                chat_type = ?,
                region = ?,
                has_topics = CASE WHEN has_topics = 1 THEN 1 ELSE ? END,
                daily_post_time = ?,
                max_posts_per_day = ?,
                cooldown_hours = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE chat_key = ?
            """,
            (
                row["chat_id"],
                row["chat_type"],
                row["region"],
                1 if row["has_topics"] else 0,
                row["daily_post_time"],
                row["max_posts_per_day"],
                row["cooldown_hours"],
                row["chat_key"],
            ),
        )

        if existing["default_topic_id"] is None and row["default_topic_id"] is not None:
            conn.execute(
                """
                UPDATE community_chats
                SET default_topic_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE chat_key = ?
                """,
                (row["default_topic_id"], row["chat_key"]),
            )

def ensure_default_content(conn) -> None:
    for item in DEFAULT_CONTENT_ITEMS:
        exists = conn.execute(
            """
            SELECT 1
            FROM community_content_items
            WHERE text = ?
            LIMIT 1
            """,
            (item["text"],),
        ).fetchone()
        if exists is None:
            repo.create_content_item(conn, **item)

def bootstrap_community_layer(conn) -> None:
    ensure_runtime_defaults(conn)
    ensure_default_chats(conn)
    ensure_default_content(conn)
