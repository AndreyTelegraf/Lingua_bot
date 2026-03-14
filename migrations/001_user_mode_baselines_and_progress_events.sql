CREATE TABLE IF NOT EXISTS user_mode_baselines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    mode TEXT NOT NULL,
    baseline_version TEXT NOT NULL,
    source_mode TEXT NOT NULL,
    source_run_id INTEGER,
    source_attempt_id INTEGER,
    estimated_vocab_size INTEGER,
    estimated_vocab_band TEXT,
    estimated_cefr_level TEXT,
    confidence REAL,
    calibration_payload_json TEXT,
    valid_from TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_until TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_mode_baselines_user_mode_active
ON user_mode_baselines(user_id, mode, is_active, id);

CREATE TABLE IF NOT EXISTS user_progress_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    mode TEXT NOT NULL,
    source_run_id INTEGER,
    source_attempt_id INTEGER,
    event_type TEXT NOT NULL,
    previous_payload_json TEXT,
    current_payload_json TEXT NOT NULL,
    delta_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_progress_events_user_mode_id
ON user_progress_events(user_id, mode, id);
