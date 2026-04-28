index|idx_vocab_answers_attempt_id|CREATE INDEX idx_vocab_answers_attempt_id
    ON vocab_answers(attempt_id)
index|idx_vocab_attempt_events_attempt|CREATE INDEX idx_vocab_attempt_events_attempt
ON vocab_attempt_events(attempt_id)
index|idx_vocab_attempt_events_attempt_id|CREATE INDEX idx_vocab_attempt_events_attempt_id
    ON vocab_attempt_events(attempt_id, created_at)
index|idx_vocab_attempt_events_event_type|CREATE INDEX idx_vocab_attempt_events_event_type
    ON vocab_attempt_events(event_type)
index|idx_vocab_attempt_events_item|CREATE INDEX idx_vocab_attempt_events_item
ON vocab_attempt_events(item_id)
index|idx_vocab_attempt_events_reason_code|CREATE INDEX idx_vocab_attempt_events_reason_code
    ON vocab_attempt_events(reason_code)
index|idx_vocab_attempt_events_user|CREATE INDEX idx_vocab_attempt_events_user
ON vocab_attempt_events(user_id)
index|idx_vocab_attempts_status_questions|CREATE INDEX idx_vocab_attempts_status_questions
    ON vocab_attempts(status, questions_answered)
index|idx_vocab_attempts_user|CREATE INDEX idx_vocab_attempts_user
ON vocab_attempts(user_id)
index|idx_vocab_attempts_user_status|CREATE INDEX idx_vocab_attempts_user_status
    ON vocab_attempts(user_id, status)
index|idx_vocab_builds_status|CREATE INDEX idx_vocab_builds_status
    ON vocab_builds(status)
index|idx_vocab_certified_inventory_v3_lemma_pos|CREATE UNIQUE INDEX idx_vocab_certified_inventory_v3_lemma_pos
ON vocab_certified_inventory_v3(LOWER(TRIM(lemma)), pos)
index|idx_vocab_certified_inventory_v3_runtime|CREATE INDEX idx_vocab_certified_inventory_v3_runtime
ON vocab_certified_inventory_v3(is_active, audit_status, pos, bin_name, freq_rank)
index|idx_vocab_choices_item_id|CREATE INDEX idx_vocab_choices_item_id
    ON vocab_choices(item_id)
index|idx_vocab_choices_item_id_position|CREATE INDEX idx_vocab_choices_item_id_position
ON vocab_choices(item_id, position_index)
index|idx_vocab_choices_v3_item_id|CREATE INDEX idx_vocab_choices_v3_item_id
ON vocab_choices_v3(item_id)
index|idx_vocab_choices_v3_item_id_position|CREATE INDEX idx_vocab_choices_v3_item_id_position
ON vocab_choices_v3(item_id, position_index)
index|idx_vocab_item_exposure_item_shown_last|CREATE INDEX idx_vocab_item_exposure_item_shown_last
ON vocab_item_exposure(item_id, shown_count, last_shown_at)
index|idx_vocab_item_exposure_last_shown_at|CREATE INDEX idx_vocab_item_exposure_last_shown_at
    ON vocab_item_exposure(last_shown_at)
index|idx_vocab_item_exposure_shown_count|CREATE INDEX idx_vocab_item_exposure_shown_count
    ON vocab_item_exposure(shown_count)
index|idx_vocab_item_validation_build_id|CREATE INDEX idx_vocab_item_validation_build_id
    ON vocab_item_validation(build_id)
index|idx_vocab_item_validation_passed|CREATE INDEX idx_vocab_item_validation_passed
    ON vocab_item_validation(passed)
index|idx_vocab_item_validation_rule_code|CREATE INDEX idx_vocab_item_validation_rule_code
    ON vocab_item_validation(rule_code)
index|idx_vocab_items_active|CREATE INDEX idx_vocab_items_active
    ON vocab_items(is_active)
index|idx_vocab_items_active_bin_freq|CREATE INDEX idx_vocab_items_active_bin_freq
ON vocab_items(is_active, bin_name, freq_rank)
index|idx_vocab_items_active_lemma_pos|CREATE INDEX idx_vocab_items_active_lemma_pos ON vocab_items(is_active, lemma, pos)
index|idx_vocab_items_active_pos_level_bin_freq|CREATE INDEX idx_vocab_items_active_pos_level_bin_freq
ON vocab_items(is_active, pos, level, bin_name, freq_rank)
index|idx_vocab_items_bin_name|CREATE INDEX idx_vocab_items_bin_name
    ON vocab_items(bin_name)
index|idx_vocab_items_cefr_estimate|CREATE INDEX idx_vocab_items_cefr_estimate ON vocab_items(cefr_estimate)
index|idx_vocab_items_concept_group|CREATE INDEX idx_vocab_items_concept_group ON vocab_items(concept_group)
index|idx_vocab_items_freq_rank|CREATE INDEX idx_vocab_items_freq_rank
    ON vocab_items(freq_rank)
index|idx_vocab_items_lemma|CREATE INDEX idx_vocab_items_lemma
    ON vocab_items(lemma)
index|idx_vocab_items_level|CREATE INDEX idx_vocab_items_level
    ON vocab_items(level)
index|idx_vocab_items_pos|CREATE INDEX idx_vocab_items_pos ON vocab_items(pos)
index|idx_vocab_lemma_candidates_build_id|CREATE INDEX idx_vocab_lemma_candidates_build_id
    ON vocab_lemma_candidates(build_id)
index|idx_vocab_lemma_candidates_gloss_key|CREATE INDEX idx_vocab_lemma_candidates_gloss_key
    ON vocab_lemma_candidates(gloss_key)
index|idx_vocab_lemma_candidates_is_eligible|CREATE INDEX idx_vocab_lemma_candidates_is_eligible
    ON vocab_lemma_candidates(is_eligible)
index|idx_vocab_lemma_candidates_lemma_key_pos|CREATE INDEX idx_vocab_lemma_candidates_lemma_key_pos
    ON vocab_lemma_candidates(lemma_key, pos)
index|idx_vocab_quarantine_build_id|CREATE INDEX idx_vocab_quarantine_build_id
    ON vocab_quarantine(build_id)
index|idx_vocab_quarantine_reason_code|CREATE INDEX idx_vocab_quarantine_reason_code
    ON vocab_quarantine(reason_code)
index|idx_vocab_quarantine_released_at|CREATE INDEX idx_vocab_quarantine_released_at
    ON vocab_quarantine(released_at)
index|idx_vocab_raw_entries_external_key|CREATE INDEX idx_vocab_raw_entries_external_key
    ON vocab_raw_entries(external_key)
index|idx_vocab_raw_entries_source_name|CREATE INDEX idx_vocab_raw_entries_source_name
    ON vocab_raw_entries(source_name)
index|idx_vocab_result_snapshots_attempt_id|CREATE INDEX idx_vocab_result_snapshots_attempt_id
    ON vocab_result_snapshots(attempt_id, step_index)
index|idx_vocab_selector_state_attempt_id|CREATE INDEX idx_vocab_selector_state_attempt_id
    ON vocab_selector_state(attempt_id)
index|sqlite_autoindex_vocab_answers_1|
index|sqlite_autoindex_vocab_attempts_1|
index|sqlite_autoindex_vocab_builds_1|
index|sqlite_autoindex_vocab_choices_1|
index|sqlite_autoindex_vocab_choices_v3_1|
index|sqlite_autoindex_vocab_selector_state_1|
table|vocab_answers|CREATE TABLE vocab_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    selected_choice_id INTEGER,
    answer_status TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, answer_kind TEXT NOT NULL DEFAULT 'selected', shown_at TEXT, answered_at TEXT,
    FOREIGN KEY (attempt_id) REFERENCES vocab_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES vocab_items(id) ON DELETE CASCADE,
    FOREIGN KEY (selected_choice_id) REFERENCES vocab_choices(id) ON DELETE SET NULL,
    UNIQUE(attempt_id, item_id)
)
table|vocab_attempt_events|CREATE TABLE vocab_attempt_events (
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
)
table|vocab_attempts|CREATE TABLE vocab_attempts (
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
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, question_limit INTEGER NOT NULL DEFAULT 24, questions_answered INTEGER NOT NULL DEFAULT 0, correct_count INTEGER NOT NULL DEFAULT 0, dont_know_count INTEGER NOT NULL DEFAULT 0, total_reject_count INTEGER NOT NULL DEFAULT 0, vocab_estimate INTEGER, cefr_estimate TEXT, hard_reject_streak INTEGER NOT NULL DEFAULT 0, product_band TEXT, result_snapshot_json TEXT,
    FOREIGN KEY (mode_run_id) REFERENCES mode_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
table|vocab_builds|CREATE TABLE vocab_builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_code TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    target_size INTEGER,
    source_snapshot_json TEXT NOT NULL DEFAULT '{}',
    config_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
)
table|vocab_certified_inventory_v3|CREATE TABLE vocab_certified_inventory_v3 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma TEXT NOT NULL,
    question_text TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    difficulty_band TEXT,
    lexical_band TEXT,
    pos TEXT NOT NULL,
    topic_tag TEXT,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    freq_rank INTEGER,
    level TEXT,
    bin_name TEXT NOT NULL,
    cefr_estimate TEXT,
    concept_group TEXT,
    donor_eligible INTEGER NOT NULL DEFAULT 0,
    source_note TEXT,
    author_note TEXT,
    audit_status TEXT NOT NULL DEFAULT 'candidate',
    audit_reasons TEXT,
    certified_at TEXT,
    certified_by TEXT,
    legacy_source_item_id INTEGER,
    CHECK (audit_status IN ('candidate','rejected','needs_rewrite','certified','retired')),
    CHECK (bin_name IN ('1K','2K','5K','10K','20K')),
    CHECK (legacy_source_item_id IS NULL)
)
table|vocab_choices|CREATE TABLE vocab_choices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    choice_text TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    position_index INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES vocab_items(id) ON DELETE CASCADE,
    UNIQUE(item_id, position_index)
)
table|vocab_choices_v3|CREATE TABLE vocab_choices_v3 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    choice_text TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    position_index INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES vocab_certified_inventory_v3(id) ON DELETE CASCADE,
    UNIQUE(item_id, position_index)
)
table|vocab_item_exposure|CREATE TABLE vocab_item_exposure (
    item_id INTEGER PRIMARY KEY,
    shown_count INTEGER NOT NULL DEFAULT 0,
    answered_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    last_shown_at TEXT,
    last_answered_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(item_id) REFERENCES vocab_items(id) ON DELETE CASCADE
)
table|vocab_item_validation|CREATE TABLE vocab_item_validation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id INTEGER NOT NULL,
    item_temp_id TEXT,
    rule_code TEXT NOT NULL,
    severity TEXT NOT NULL,
    passed INTEGER NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(build_id) REFERENCES vocab_builds(id) ON DELETE CASCADE
)
table|vocab_items|CREATE TABLE vocab_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lemma TEXT NOT NULL,
    question_text TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    difficulty_band TEXT,
    lexical_band TEXT,
    pos TEXT,
    topic_tag TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
, freq_rank INTEGER, level TEXT, bin_name TEXT, cefr_estimate TEXT, concept_group TEXT, donor_eligible INTEGER)
table|vocab_lemma_candidates|CREATE TABLE vocab_lemma_candidates (
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
)
table|vocab_quarantine|CREATE TABLE vocab_quarantine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id INTEGER,
    lemma TEXT,
    pos TEXT,
    reason_code TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    released_at TEXT,
    FOREIGN KEY(build_id) REFERENCES vocab_builds(id) ON DELETE SET NULL
)
table|vocab_raw_entries|CREATE TABLE vocab_raw_entries (
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
)
table|vocab_result_snapshots|CREATE TABLE vocab_result_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL,
    step_index INTEGER NOT NULL,
    estimated_vocab_band TEXT,
    estimated_vocab_size INTEGER,
    confidence REAL,
    snapshot_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES vocab_attempts(id) ON DELETE CASCADE
)
table|vocab_selector_state|CREATE TABLE vocab_selector_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL UNIQUE,
    selector_payload_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, shown_item_ids_json TEXT NOT NULL DEFAULT '[]', pos_counters_json TEXT NOT NULL DEFAULT '{}', cefr_counters_json TEXT NOT NULL DEFAULT '{}', bin_counters_json TEXT NOT NULL DEFAULT '{}', current_item_meta_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (attempt_id) REFERENCES vocab_attempts(id) ON DELETE CASCADE
)
view|vocab_items_runtime_v3|CREATE VIEW vocab_items_runtime_v3 AS
SELECT
    id,
    lemma,
    question_text,
    correct_answer,
    difficulty_band,
    lexical_band,
    pos,
    topic_tag,
    is_active,
    created_at,
    updated_at,
    freq_rank,
    level,
    bin_name,
    cefr_estimate,
    concept_group,
    donor_eligible
FROM vocab_certified_inventory_v3
WHERE is_active = 1
  AND audit_status = 'certified'
