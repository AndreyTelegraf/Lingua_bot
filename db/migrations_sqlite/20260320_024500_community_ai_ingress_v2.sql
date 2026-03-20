ALTER TABLE community_thread_events ADD COLUMN message_thread_id INTEGER;
ALTER TABLE community_thread_events ADD COLUMN reply_to_message_id INTEGER;
ALTER TABLE community_thread_events ADD COLUMN message_text TEXT;

CREATE INDEX IF NOT EXISTS idx_community_thread_events_thread_root_created
    ON community_thread_events(thread_root_message_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uidx_community_thread_events_chat_message
    ON community_thread_events(chat_id, message_id);
