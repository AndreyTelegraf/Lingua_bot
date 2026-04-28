CREATE TABLE IF NOT EXISTS vocab_certified_inventory_v3 (
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
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vocab_certified_inventory_v3_lemma_pos
ON vocab_certified_inventory_v3(LOWER(TRIM(lemma)), pos);

CREATE INDEX IF NOT EXISTS idx_vocab_certified_inventory_v3_runtime
ON vocab_certified_inventory_v3(is_active, audit_status, pos, bin_name, freq_rank);

DROP VIEW IF EXISTS vocab_items_runtime_v3;

CREATE VIEW vocab_items_runtime_v3 AS
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
  AND audit_status = 'certified';
