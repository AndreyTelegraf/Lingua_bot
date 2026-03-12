CREATE TABLE IF NOT EXISTS vocab_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode_run_id INTEGER NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    aborted_at TEXT,
    current_step INTEGER NOT NULL DEFAULT 0,
    estimated_vocab_band TEXT,
    estimated_vocab_size INTEGER,
    confidence REAL,
    completion_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mode_run_id) REFERENCES mode_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vocab_attempts_user_status
    ON vocab_attempts(user_id, status);

CREATE TABLE IF NOT EXISTS vocab_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    selected_choice_id INTEGER,
    answer_status TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES vocab_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES vocab_items(id) ON DELETE CASCADE,
    FOREIGN KEY (selected_choice_id) REFERENCES vocab_choices(id) ON DELETE SET NULL,
    UNIQUE(attempt_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_vocab_answers_attempt_id
    ON vocab_answers(attempt_id);
