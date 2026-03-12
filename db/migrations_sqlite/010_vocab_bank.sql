CREATE TABLE IF NOT EXISTS vocab_items (
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
);

CREATE INDEX IF NOT EXISTS idx_vocab_items_active
    ON vocab_items(is_active);

CREATE INDEX IF NOT EXISTS idx_vocab_items_lemma
    ON vocab_items(lemma);

CREATE TABLE IF NOT EXISTS vocab_choices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    choice_text TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    position_index INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES vocab_items(id) ON DELETE CASCADE,
    UNIQUE(item_id, position_index)
);

CREATE INDEX IF NOT EXISTS idx_vocab_choices_item_id
    ON vocab_choices(item_id);
