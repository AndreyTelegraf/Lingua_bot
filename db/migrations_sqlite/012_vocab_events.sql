CREATE TABLE IF NOT EXISTS vocab_attempt_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    step_index INTEGER,
    item_id INTEGER,
    reason_code TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES vocab_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vocab_attempt_events_attempt_id
    ON vocab_attempt_events(attempt_id, created_at);

CREATE TABLE IF NOT EXISTS vocab_selector_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL UNIQUE,
    selector_payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES vocab_attempts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS vocab_result_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    step_index INTEGER NOT NULL,
    estimated_vocab_band TEXT,
    estimated_vocab_size INTEGER,
    confidence REAL,
    snapshot_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES vocab_attempts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vocab_result_snapshots_attempt_id
    ON vocab_result_snapshots(attempt_id, step_index);
