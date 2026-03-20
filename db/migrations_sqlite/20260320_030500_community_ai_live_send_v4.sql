CREATE TABLE IF NOT EXISTS community_ai_reply_delivery_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    post_log_id INTEGER,
    plan_log_id INTEGER NOT NULL UNIQUE,
    trigger_message_id INTEGER,
    reply_to_message_id INTEGER,
    sent_message_id INTEGER,
    delivery_status TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    response_id TEXT,
    used_fallback INTEGER NOT NULL DEFAULT 0,
    delivered_text TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES community_chats(chat_id) ON DELETE CASCADE,
    FOREIGN KEY (post_log_id) REFERENCES community_post_log(id) ON DELETE SET NULL,
    FOREIGN KEY (plan_log_id) REFERENCES community_ai_reply_plan_log(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_community_ai_reply_delivery_log_post_created
    ON community_ai_reply_delivery_log(post_log_id, created_at DESC);

INSERT OR IGNORE INTO community_runtime_config(key, value_text) VALUES ('ai_live_enabled', '0');
INSERT OR IGNORE INTO community_runtime_config(key, value_text) VALUES ('ai_reply_cooldown_seconds', '900');
INSERT OR IGNORE INTO community_runtime_config(key, value_text) VALUES ('ai_max_generated_chars', '220');
INSERT OR IGNORE INTO community_runtime_config(key, value_text) VALUES ('ai_fallback_to_planner_text', '1');
