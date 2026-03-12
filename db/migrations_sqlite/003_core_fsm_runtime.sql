CREATE TABLE IF NOT EXISTS fsm_runtime_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    run_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0,
    current_item_id TEXT,
    expected_callback_token TEXT,
    expected_message_id INTEGER,
    revision INTEGER NOT NULL DEFAULT 0,
    locked_by TEXT,
    lock_acquired_at TEXT,
    last_transition_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES mode_runs(id) ON DELETE CASCADE,
    UNIQUE(mode, user_id),
    UNIQUE(run_id)
);

CREATE INDEX IF NOT EXISTS idx_fsm_runtime_mode_status
    ON fsm_runtime_state(mode, status);

CREATE TABLE IF NOT EXISTS user_mode_priors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    last_vocab_run_id INTEGER,
    last_vocab_band TEXT,
    vocab_confidence REAL,
    recommended_level_start_band TEXT,
    last_level_run_id INTEGER,
    last_level_cefr TEXT,
    level_confidence REAL,
    ciple_readiness TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_assessment_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    profile_payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
