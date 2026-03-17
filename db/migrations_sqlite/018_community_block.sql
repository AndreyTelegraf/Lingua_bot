CREATE TABLE IF NOT EXISTS community_runtime_config (
    key TEXT PRIMARY KEY,
    value_text TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS community_chats (
    chat_id INTEGER PRIMARY KEY,
    chat_key TEXT NOT NULL UNIQUE,
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

CREATE INDEX IF NOT EXISTS idx_community_chats_enabled
    ON community_chats(is_enabled, chat_key);

CREATE TABLE IF NOT EXISTS community_content_items (
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

CREATE INDEX IF NOT EXISTS idx_community_content_active_region
    ON community_content_items(is_active, region, format_type, priority);

CREATE TABLE IF NOT EXISTS community_post_log (
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
    thread_reactivated_after_followup INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (chat_id) REFERENCES community_chats(chat_id) ON DELETE CASCADE,
    FOREIGN KEY (content_id) REFERENCES community_content_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_community_post_log_chat_posted
    ON community_post_log(chat_id, posted_at DESC);

CREATE INDEX IF NOT EXISTS idx_community_post_log_chat_content_posted
    ON community_post_log(chat_id, content_id, posted_at DESC);

CREATE TABLE IF NOT EXISTS community_thread_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    post_log_id INTEGER,
    thread_root_message_id INTEGER,
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES community_chats(chat_id) ON DELETE CASCADE,
    FOREIGN KEY (post_log_id) REFERENCES community_post_log(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_community_thread_events_chat_created
    ON community_thread_events(chat_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_community_thread_events_post_created
    ON community_thread_events(post_log_id, created_at DESC);

INSERT OR IGNORE INTO community_runtime_config(key, value_text) VALUES
    ('global_enabled', '1'),
    ('followups_enabled', '0'),
    ('default_mode', 'A');
