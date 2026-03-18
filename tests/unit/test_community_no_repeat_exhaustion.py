from __future__ import annotations

import sqlite3

from services.community_block.bootstrap import bootstrap_community_layer
from services.community_block.decision import choose_post_candidate
from services.community_block import repo


def build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.executescript(
        """
        CREATE TABLE community_runtime_config (
            key TEXT PRIMARY KEY,
            value_text TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE community_chats (
            chat_id INTEGER PRIMARY KEY,
            chat_key TEXT NOT NULL,
            chat_type TEXT NOT NULL,
            region TEXT,
            has_topics INTEGER NOT NULL DEFAULT 0,
            default_topic_id INTEGER,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            daily_post_time TEXT NOT NULL DEFAULT '11:00',
            max_posts_per_day INTEGER NOT NULL DEFAULT 1,
            cooldown_hours INTEGER NOT NULL DEFAULT 24,
            last_posted_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE community_content_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            format_type TEXT NOT NULL,
            topic TEXT,
            region TEXT,
            has_question INTEGER NOT NULL DEFAULT 0,
            difficulty TEXT NOT NULL DEFAULT 'light',
            is_active INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE community_post_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            content_id INTEGER NOT NULL,
            thread_root_message_id INTEGER,
            posted_message_id INTEGER,
            posted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            had_replies INTEGER NOT NULL DEFAULT 0,
            replies_count INTEGER NOT NULL DEFAULT 0,
            unique_users_count INTEGER NOT NULL DEFAULT 0,
            reply_latency_first_sec INTEGER,
            thread_depth_max INTEGER NOT NULL DEFAULT 0,
            followup_sent INTEGER NOT NULL DEFAULT 0,
            followup_posted_at TEXT,
            thread_reactivated_after_followup INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE community_thread_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            post_log_id INTEGER,
            thread_root_message_id INTEGER,
            message_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    bootstrap_community_layer(conn)
    repo.enable_only_chat(conn, chat_key="chatalgarve")
    conn.execute(
        """
        UPDATE community_chats
        SET cooldown_hours = 0,
            last_posted_at = '2026-03-01 00:00:00'
        WHERE chat_key = 'chatalgarve'
        """
    )
    conn.commit()
    return conn


def test_choose_post_candidate_prefers_unused_before_reuse() -> None:
    conn = build_conn()
    chat = repo.get_chat_by_key(conn, chat_key="chatalgarve")
    assert chat is not None

    first = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=True)
    assert first.allowed is True
    assert first.reason == "candidate_selected_fresh"
    assert first.content_id == 1

    repo.log_post(
        conn,
        chat_id=int(chat["chat_id"]),
        content_id=int(first.content_id),
        thread_root_message_id=1001,
        posted_message_id=1001,
    )
    conn.execute(
        """
        UPDATE community_chats
        SET cooldown_hours = 0,
            last_posted_at = '2026-03-01 00:00:00'
        WHERE chat_key = 'chatalgarve'
        """
    )
    conn.commit()

    chat = repo.get_chat_by_key(conn, chat_key="chatalgarve")
    second = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=True)
    assert second.allowed is True
    assert second.reason == "candidate_selected_fresh"
    assert second.content_id == 2

    repo.log_post(
        conn,
        chat_id=int(chat["chat_id"]),
        content_id=int(second.content_id),
        thread_root_message_id=1002,
        posted_message_id=1002,
    )
    conn.execute(
        """
        UPDATE community_chats
        SET cooldown_hours = 0,
            last_posted_at = '2026-03-01 00:00:00'
        WHERE chat_key = 'chatalgarve'
        """
    )
    conn.commit()

    chat = repo.get_chat_by_key(conn, chat_key="chatalgarve")
    third = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=True)
    assert third.allowed is True
    assert third.reason == "candidate_selected_fresh"
    assert third.content_id == 3

    repo.log_post(
        conn,
        chat_id=int(chat["chat_id"]),
        content_id=int(third.content_id),
        thread_root_message_id=1003,
        posted_message_id=1003,
    )
    conn.execute(
        """
        UPDATE community_chats
        SET cooldown_hours = 0,
            last_posted_at = '2026-03-01 00:00:00'
        WHERE chat_key = 'chatalgarve'
        """
    )
    conn.commit()

    chat = repo.get_chat_by_key(conn, chat_key="chatalgarve")
    fourth = choose_post_candidate(conn, chat=chat, recent_messages_count=0, dry_run=True)
    assert fourth.allowed is True
    assert fourth.reason == "candidate_selected_reuse_after_exhaustion"
    assert fourth.content_id in {1, 2, 3}
