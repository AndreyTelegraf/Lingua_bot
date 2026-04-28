CREATE TABLE IF NOT EXISTS vocab_choices_v3 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    choice_text TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    position_index INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES vocab_certified_inventory_v3(id) ON DELETE CASCADE,
    UNIQUE(item_id, position_index)
);

CREATE INDEX IF NOT EXISTS idx_vocab_choices_v3_item_id
ON vocab_choices_v3(item_id);

CREATE INDEX IF NOT EXISTS idx_vocab_choices_v3_item_id_position
ON vocab_choices_v3(item_id, position_index);
