PRAGMA foreign_keys=OFF;
BEGIN;

DROP VIEW IF EXISTS vocab_items_runtime_v3;
DROP VIEW IF EXISTS vocab_items_runtime;

DROP TABLE IF EXISTS vocab_choices_v3;
DROP TABLE IF EXISTS vocab_certified_inventory_v3;
DROP TABLE IF EXISTS vocab_item_diagnostic_audit;
DROP TABLE IF EXISTS vocab_item_exposure;
DROP TABLE IF EXISTS vocab_selector_state;
DROP TABLE IF EXISTS vocab_answers;
DROP TABLE IF EXISTS vocab_attempt_events;
DROP TABLE IF EXISTS vocab_attempts;
DROP TABLE IF EXISTS vocab_choices;
DROP TABLE IF EXISTS vocab_items;

DELETE FROM schema_migrations WHERE lower(filename) LIKE '%vocab%';

COMMIT;
PRAGMA foreign_keys=ON;
