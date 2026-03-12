ALTER TABLE vocab_items ADD COLUMN freq_rank INTEGER;
ALTER TABLE vocab_items ADD COLUMN level TEXT;
ALTER TABLE vocab_items ADD COLUMN bin_name TEXT;

ALTER TABLE vocab_attempts ADD COLUMN question_limit INTEGER NOT NULL DEFAULT 24;
ALTER TABLE vocab_attempts ADD COLUMN questions_answered INTEGER NOT NULL DEFAULT 0;
ALTER TABLE vocab_attempts ADD COLUMN correct_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE vocab_attempts ADD COLUMN dont_know_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE vocab_attempts ADD COLUMN total_reject_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE vocab_attempts ADD COLUMN vocab_estimate INTEGER;
ALTER TABLE vocab_attempts ADD COLUMN cefr_estimate TEXT;

ALTER TABLE vocab_answers ADD COLUMN answer_kind TEXT NOT NULL DEFAULT 'selected';
ALTER TABLE vocab_answers ADD COLUMN shown_at TEXT;
ALTER TABLE vocab_answers ADD COLUMN answered_at TEXT;

CREATE INDEX IF NOT EXISTS idx_vocab_items_freq_rank
    ON vocab_items(freq_rank);

CREATE INDEX IF NOT EXISTS idx_vocab_items_level
    ON vocab_items(level);

CREATE INDEX IF NOT EXISTS idx_vocab_items_bin_name
    ON vocab_items(bin_name);
