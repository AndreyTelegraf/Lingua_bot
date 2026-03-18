from __future__ import annotations

import sqlite3

from services.community_block import bootstrap, repo


def build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS community_runtime_config (
            key TEXT PRIMARY KEY,
            value_text TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS community_chats (
            chat_id INTEGER NOT NULL UNIQUE,
            chat_key TEXT NOT NULL UNIQUE,
            chat_type TEXT NOT NULL,
            region TEXT,
            has_topics INTEGER NOT NULL DEFAULT 0,
            default_topic_id INTEGER,
            is_enabled INTEGER NOT NULL DEFAULT 0,
            daily_post_time TEXT NOT NULL DEFAULT '11:00',
            max_posts_per_day INTEGER NOT NULL DEFAULT 1,
            cooldown_hours INTEGER NOT NULL DEFAULT 24,
            last_posted_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS community_content_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            format_type TEXT NOT NULL,
            topic TEXT,
            region TEXT,
            has_question INTEGER NOT NULL DEFAULT 1,
            difficulty TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 50,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS community_post_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            content_id INTEGER NOT NULL,
            thread_root_message_id INTEGER,
            posted_message_id INTEGER NOT NULL,
            posted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        '''
    )
    bootstrap.bootstrap_community_layer(conn)
    return conn


def test_bind_chat_persists_topic_fields() -> None:
    conn = build_conn()
    repo.bind_chat_identity(
        conn,
        chat_key="chatlisboa",
        real_chat_id=-1001656765898,
        has_topics=True,
        default_topic_id=12345,
    )
    row = repo.get_chat_by_key(conn, chat_key="chatlisboa")
    assert row is not None
    assert int(row["has_topics"]) == 1
    assert int(row["default_topic_id"]) == 12345
