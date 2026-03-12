ALTER TABLE vocab_attempts ADD COLUMN hard_reject_streak INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_vocab_attempts_status_questions
    ON vocab_attempts(status, questions_answered);

CREATE INDEX IF NOT EXISTS idx_vocab_attempt_events_event_type
    ON vocab_attempt_events(event_type);

CREATE INDEX IF NOT EXISTS idx_vocab_attempt_events_reason_code
    ON vocab_attempt_events(reason_code);
