CREATE TABLE IF NOT EXISTS community_ai_reply_plan_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    post_log_id INTEGER,
    thread_root_message_id INTEGER,
    trigger_message_id INTEGER,
    planner_version TEXT NOT NULL,
    plan_status TEXT NOT NULL,
    should_reply INTEGER NOT NULL DEFAULT 0,
    reply_mode TEXT,
    confidence REAL,
    risk_level TEXT,
    product_bridge_allowed INTEGER NOT NULL DEFAULT 0,
    human_like_score REAL,
    verbosity_score REAL,
    canned_pattern_score REAL,
    prompt_payload_json TEXT,
    candidates_json TEXT,
    selected_reply_text TEXT,
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES community_chats(chat_id) ON DELETE CASCADE,
    FOREIGN KEY (post_log_id) REFERENCES community_post_log(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_community_ai_reply_plan_log_post_created
    ON community_ai_reply_plan_log(post_log_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_community_ai_reply_plan_log_chat_created
    ON community_ai_reply_plan_log(chat_id, created_at DESC);

INSERT OR IGNORE INTO community_runtime_config(key, value_text) VALUES ('ai_replies_enabled', '0');
INSERT OR IGNORE INTO community_runtime_config(key, value_text) VALUES ('ai_provider', 'openai');
INSERT OR IGNORE INTO community_runtime_config(key, value_text) VALUES ('ai_model', '');
INSERT OR IGNORE INTO community_runtime_config(key, value_text) VALUES ('ai_dry_run', '1');
INSERT OR IGNORE INTO community_runtime_config(key, value_text) VALUES ('ai_min_user_replies', '1');
INSERT OR IGNORE INTO community_runtime_config(key, value_text) VALUES ('ai_max_plans_per_thread', '2');
