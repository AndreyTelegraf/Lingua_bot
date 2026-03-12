CREATE TABLE IF NOT EXISTS vocab_item_exposure (
    item_id INTEGER PRIMARY KEY,
    shown_count INTEGER NOT NULL DEFAULT 0,
    answered_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    last_shown_at TEXT,
    last_answered_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(item_id) REFERENCES vocab_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vocab_item_exposure_shown_count
    ON vocab_item_exposure(shown_count);

CREATE INDEX IF NOT EXISTS idx_vocab_item_exposure_last_shown_at
    ON vocab_item_exposure(last_shown_at);
