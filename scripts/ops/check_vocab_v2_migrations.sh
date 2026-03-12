#!/usr/bin/env bash
set -euo pipefail

DB="${1:-./data/lingua_staging.db}"

echo
echo "=== DB FILE ==="
ls -l "$DB"

echo
echo "=== SQLITE VERSION ==="
sqlite3 "$DB" "select sqlite_version();"

echo
echo "=== APPLIED MIGRATIONS ==="
sqlite3 -header -column "$DB" "
SELECT version, applied_at
FROM schema_migrations
WHERE version IN (
  '013_vocab_contract_v2.sql',
  '014_vocab_selector_runtime.sql',
  '015_vocab_rejects_and_result_fields.sql'
)
ORDER BY version;
"

echo
echo "=== vocab_items COLUMNS ==="
sqlite3 -header -column "$DB" "PRAGMA table_info(vocab_items);"

echo
echo "=== vocab_attempts COLUMNS ==="
sqlite3 -header -column "$DB" "PRAGMA table_info(vocab_attempts);"

echo
echo "=== vocab_answers COLUMNS ==="
sqlite3 -header -column "$DB" "PRAGMA table_info(vocab_answers);"

echo
echo "=== vocab_selector_state COLUMNS ==="
sqlite3 -header -column "$DB" "PRAGMA table_info(vocab_selector_state);"

echo
echo "=== CHECK 013 TARGET COLUMNS ==="
for col in freq_rank level bin_name; do
  n=$(sqlite3 "$DB" "SELECT COUNT(*) FROM pragma_table_info('vocab_items') WHERE name='$col';")
  printf "vocab_items.%-22s %s\n" "$col" "$n"
done
for col in question_limit questions_answered correct_count dont_know_count total_reject_count vocab_estimate cefr_estimate; do
  n=$(sqlite3 "$DB" "SELECT COUNT(*) FROM pragma_table_info('vocab_attempts') WHERE name='$col';")
  printf "vocab_attempts.%-17s %s\n" "$col" "$n"
done
for col in answer_kind shown_at answered_at; do
  n=$(sqlite3 "$DB" "SELECT COUNT(*) FROM pragma_table_info('vocab_answers') WHERE name='$col';")
  printf "vocab_answers.%-20s %s\n" "$col" "$n"
done

echo
echo "=== CHECK 014 TARGET COLUMNS ==="
for col in shown_item_ids_json pos_counters_json cefr_counters_json bin_counters_json current_item_meta_json; do
  n=$(sqlite3 "$DB" "SELECT COUNT(*) FROM pragma_table_info('vocab_selector_state') WHERE name='$col';")
  printf "vocab_selector_state.%-12s %s\n" "$col" "$n"
done

echo
echo "=== CHECK 015 TARGET COLUMNS ==="
for col in hard_reject_streak; do
  n=$(sqlite3 "$DB" "SELECT COUNT(*) FROM pragma_table_info('vocab_attempts') WHERE name='$col';")
  printf "vocab_attempts.%-17s %s\n" "$col" "$n"
done

echo
echo "=== INDEX CHECK ==="
for idx in \
  idx_vocab_items_freq_rank \
  idx_vocab_items_level \
  idx_vocab_items_bin_name \
  idx_vocab_selector_state_attempt_id \
  idx_vocab_attempts_status_questions \
  idx_vocab_attempt_events_event_type \
  idx_vocab_attempt_events_reason_code
do
  n=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name='$idx';")
  printf "%-40s %s\n" "$idx" "$n"
done

echo
echo "=== SAFETY SUMMARY ==="
echo "Rule:"
echo "- if target column count is 0 and migration not applied -> safe to apply"
echo "- if target column count is 1 and migration not applied -> migration will fail on duplicate column"
echo "- if migration already applied -> do not rerun"
