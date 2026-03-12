CREATE TABLE IF NOT EXISTS vocab_raw_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    external_key TEXT,
    raw_lemma TEXT,
    raw_pos TEXT,
    raw_level TEXT,
    raw_freq TEXT,
    raw_gloss_ru TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vocab_raw_entries_source_name
    ON vocab_raw_entries(source_name);

CREATE INDEX IF NOT EXISTS idx_vocab_raw_entries_external_key
    ON vocab_raw_entries(external_key);

CREATE TABLE IF NOT EXISTS vocab_lemma_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id INTEGER,
    source_name TEXT NOT NULL,
    source_weight REAL,
    merge_group_id TEXT,
    normalized_lemma TEXT NOT NULL,
    lemma_key TEXT NOT NULL,
    pos TEXT,
    level TEXT,
    freq_rank INTEGER,
    ru_gloss TEXT,
    gloss_key TEXT,
    is_eligible INTEGER NOT NULL DEFAULT 1,
    reject_reason TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(build_id) REFERENCES vocab_builds(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_vocab_lemma_candidates_build_id
    ON vocab_lemma_candidates(build_id);

CREATE INDEX IF NOT EXISTS idx_vocab_lemma_candidates_lemma_key_pos
    ON vocab_lemma_candidates(lemma_key, pos);

CREATE INDEX IF NOT EXISTS idx_vocab_lemma_candidates_gloss_key
    ON vocab_lemma_candidates(gloss_key);

CREATE INDEX IF NOT EXISTS idx_vocab_lemma_candidates_is_eligible
    ON vocab_lemma_candidates(is_eligible);

CREATE TABLE IF NOT EXISTS vocab_builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_code TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    target_size INTEGER,
    source_snapshot_json TEXT NOT NULL DEFAULT '{}',
    config_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_vocab_builds_status
    ON vocab_builds(status);

CREATE TABLE IF NOT EXISTS vocab_item_validation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id INTEGER NOT NULL,
    item_temp_id TEXT,
    rule_code TEXT NOT NULL,
    severity TEXT NOT NULL,
    passed INTEGER NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(build_id) REFERENCES vocab_builds(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vocab_item_validation_build_id
    ON vocab_item_validation(build_id);

CREATE INDEX IF NOT EXISTS idx_vocab_item_validation_rule_code
    ON vocab_item_validation(rule_code);

CREATE INDEX IF NOT EXISTS idx_vocab_item_validation_passed
    ON vocab_item_validation(passed);

CREATE TABLE IF NOT EXISTS vocab_quarantine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id INTEGER,
    lemma TEXT,
    pos TEXT,
    reason_code TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    released_at TEXT,
    FOREIGN KEY(build_id) REFERENCES vocab_builds(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_vocab_quarantine_build_id
    ON vocab_quarantine(build_id);

CREATE INDEX IF NOT EXISTS idx_vocab_quarantine_reason_code
    ON vocab_quarantine(reason_code);

CREATE INDEX IF NOT EXISTS idx_vocab_quarantine_released_at
    ON vocab_quarantine(released_at);
