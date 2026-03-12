CREATE TABLE IF NOT EXISTS mode_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    aborted_at TEXT,
    source TEXT,
    source_run_id INTEGER,
    prior_payload_json TEXT,
    result_payload_json TEXT,
    completion_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mode_runs_user_mode_status
    ON mode_runs(user_id, mode, status);

CREATE INDEX IF NOT EXISTS idx_mode_runs_started_at
    ON mode_runs(started_at);

CREATE TABLE IF NOT EXISTS mode_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    run_id INTEGER NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    result_version TEXT NOT NULL DEFAULT 'v1',
    score_numeric REAL,
    band_text TEXT,
    cefr_level TEXT,
    confidence REAL,
    result_payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES mode_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mode_results_user_mode
    ON mode_results(user_id, mode);

CREATE TABLE IF NOT EXISTS attempt_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    run_id INTEGER,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    status_from TEXT,
    status_to TEXT,
    step_index INTEGER,
    item_id TEXT,
    reason_code TEXT,
    payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES mode_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_attempt_events_mode_run
    ON attempt_events(mode, run_id, created_at);

CREATE INDEX IF NOT EXISTS idx_attempt_events_user_mode
    ON attempt_events(user_id, mode, created_at);
