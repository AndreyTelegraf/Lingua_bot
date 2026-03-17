from __future__ import annotations

from services.community_block import repo
from services.community_block.models import COMMUNITY_RUNTIME_KEYS
from services.community_block.registry import DEFAULT_COMMUNITY_CHAT_KEYS

DEFAULT_CHAT_DEFINITIONS: tuple[dict[str, object], ...] = (
    {
        "chat_id": -100001,
        "chat_key": "left4portugal",
        "chat_type": "global",
        "region": None,
        "has_topics": False,
        "default_topic_id": None,
        "is_enabled": False,
        "daily_post_time": "11:00",
        "max_posts_per_day": 1,
        "cooldown_hours": 24,
    },
    {
        "chat_id": -100002,
        "chat_key": "chatlisboa",
        "chat_type": "local",
        "region": "lisboa",
        "has_topics": False,
        "default_topic_id": None,
        "is_enabled": False,
        "daily_post_time": "11:00",
        "max_posts_per_day": 1,
        "cooldown_hours": 24,
    },
    {
        "chat_id": -100003,
        "chat_key": "chatporto",
        "chat_type": "local",
        "region": "porto",
        "has_topics": False,
        "default_topic_id": None,
        "is_enabled": False,
        "daily_post_time": "11:00",
        "max_posts_per_day": 1,
        "cooldown_hours": 24,
    },
    {
        "chat_id": -100004,
        "chat_key": "chatleiria",
        "chat_type": "local",
        "region": "leiria",
        "has_topics": False,
        "default_topic_id": None,
        "is_enabled": False,
        "daily_post_time": "11:00",
        "max_posts_per_day": 1,
        "cooldown_hours": 24,
    },
    {
        "chat_id": -100005,
        "chat_key": "chatalgarve",
        "chat_type": "local",
        "region": "algarve",
        "has_topics": False,
        "default_topic_id": None,
        "is_enabled": False,
        "daily_post_time": "11:00",
        "max_posts_per_day": 1,
        "cooldown_hours": 24,
    },
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
        repo.upsert_chat(conn, **row)

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
