CREATE TABLE IF NOT EXISTS vocab4_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma TEXT NOT NULL,
    pos TEXT NOT NULL CHECK (pos IN ('noun', 'verb', 'adjective', 'adverb')),
    bin_name TEXT NOT NULL CHECK (bin_name IN ('1K', '2K', '5K', '10K', '20K')),
    cefr_hint TEXT,
    prompt TEXT NOT NULL,
    correct_choice TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
    cert_status TEXT NOT NULL DEFAULT 'draft' CHECK (cert_status IN ('draft', 'rejected', 'needs_rewrite', 'certified', 'retired')),
    diagnostic_tags TEXT NOT NULL DEFAULT '{}',
    freq_rank INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lemma, pos, bin_name)
);

CREATE INDEX IF NOT EXISTS idx_vocab4_items_active_cert
    ON vocab4_items(is_active, cert_status);

CREATE INDEX IF NOT EXISTS idx_vocab4_items_pos
    ON vocab4_items(pos);

CREATE INDEX IF NOT EXISTS idx_vocab4_items_bin_name
    ON vocab4_items(bin_name);

CREATE TABLE IF NOT EXISTS vocab4_choices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    choice_text TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0 CHECK (is_correct IN (0, 1)),
    position_index INTEGER NOT NULL CHECK (position_index BETWEEN 0 AND 5),
    FOREIGN KEY (item_id) REFERENCES vocab4_items(id) ON DELETE CASCADE,
    UNIQUE(item_id, position_index)
);

CREATE INDEX IF NOT EXISTS idx_vocab4_choices_item_id
    ON vocab4_choices(item_id);

CREATE TABLE IF NOT EXISTS vocab4_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'finished', 'abandoned', 'failed')),
    current_step INTEGER NOT NULL DEFAULT 0,
    question_limit INTEGER NOT NULL DEFAULT 24,
    selector_state_json TEXT NOT NULL DEFAULT '{}',
    result_snapshot_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vocab4_attempts_user_status
    ON vocab4_attempts(user_id, status);

CREATE TABLE IF NOT EXISTS vocab4_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    selected_choice_id INTEGER,
    is_correct INTEGER NOT NULL DEFAULT 0,
    answer_kind TEXT NOT NULL DEFAULT 'selected',
    latency_ms INTEGER,
    shown_at TEXT,
    answered_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES vocab4_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES vocab4_items(id),
    UNIQUE(attempt_id, item_id)
);

CREATE INDEX IF NOT EXISTS idx_vocab4_answers_attempt_id
    ON vocab4_answers(attempt_id);

CREATE TABLE IF NOT EXISTS vocab4_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    item_id INTEGER,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES vocab4_attempts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vocab4_events_attempt_id
    ON vocab4_events(attempt_id);

CREATE INDEX IF NOT EXISTS idx_vocab4_events_event_type
    ON vocab4_events(event_type);

CREATE TABLE IF NOT EXISTS vocab4_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    questions_answered INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    pos_breakdown_json TEXT NOT NULL DEFAULT '{}',
    bin_breakdown_json TEXT NOT NULL DEFAULT '{}',
    vocab_estimate INTEGER,
    cefr_estimate TEXT,
    diagnostic_profile_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES vocab4_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vocab4_results_user_id
    ON vocab4_results(user_id);

CREATE TABLE IF NOT EXISTS vocab4_authoring_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    lemma TEXT NOT NULL,
    pos TEXT,
    bin_name TEXT,
    cefr_hint TEXT,
    prompt TEXT,
    correct_choice TEXT,
    distractors_json TEXT NOT NULL DEFAULT '[]',
    cert_status TEXT NOT NULL DEFAULT 'pending',
    reject_reason TEXT,
    reviewer_notes TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    promoted_item_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (promoted_item_id) REFERENCES vocab4_items(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_vocab4_authoring_items_cert_status
    ON vocab4_authoring_items(cert_status);

CREATE INDEX IF NOT EXISTS idx_vocab4_authoring_items_source_name
    ON vocab4_authoring_items(source_name);

CREATE TABLE IF NOT EXISTS vocab4_certification_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    authoring_item_id INTEGER NOT NULL,
    reviewer_id TEXT,
    decision TEXT NOT NULL,
    rule_codes_json TEXT NOT NULL DEFAULT '[]',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (authoring_item_id) REFERENCES vocab4_authoring_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vocab4_cert_reviews_authoring_item_id
    ON vocab4_certification_reviews(authoring_item_id);

CREATE INDEX IF NOT EXISTS idx_vocab4_cert_reviews_decision
    ON vocab4_certification_reviews(decision);
