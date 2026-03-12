ALTER TABLE vocab_selector_state ADD COLUMN shown_item_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE vocab_selector_state ADD COLUMN pos_counters_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE vocab_selector_state ADD COLUMN cefr_counters_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE vocab_selector_state ADD COLUMN bin_counters_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE vocab_selector_state ADD COLUMN current_item_meta_json TEXT NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_vocab_selector_state_attempt_id
    ON vocab_selector_state(attempt_id);
