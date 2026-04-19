#!/usr/bin/env bash
# adverb_5k_rebuild_apply_DONOTRUN.sh
# Applies distractor rebuild for 6 inactive 5K adverb items.
# Dry-run by default. Pass --apply to execute.
# Gate: run adverb_5k_rebuild_stage3_validate.py first and confirm PASS.
# DO NOT run without operator review of adverb_5k_rebuild_manifest.json.

set -euo pipefail

DB="${1:-data/lingua_staging.db}"
APPLY=0
if [[ "${2:-}" == "--apply" ]]; then
  APPLY=1
fi

if [[ "$APPLY" -eq 0 ]]; then
  echo "DRY-RUN MODE: No changes will be made. Pass --apply as second argument to execute."
fi

echo "--- id=3958 frequentemente -> часто ---"
echo "  DELETE 6 existing choices"
echo "  INSERT choice_text='часто' is_correct=1 pos=0"
echo "  INSERT choice_text='редко' is_correct=0 pos=1"
echo "  INSERT choice_text='иногда' is_correct=0 pos=2"
echo "  INSERT choice_text='давно' is_correct=0 pos=3"
if [[ "$APPLY" -eq 1 ]]; then
  sqlite3 "$DB" "DELETE FROM vocab_choices WHERE item_id=3958;"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3958, 'часто', 1, 0);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3958, 'редко', 0, 1);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3958, 'иногда', 0, 2);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3958, 'давно', 0, 3);"
  echo "  APPLIED id=3958"
fi

echo "--- id=3960 geralmente -> обычно ---"
echo "  DELETE 6 existing choices"
echo "  INSERT choice_text='обычно' is_correct=1 pos=0"
echo "  INSERT choice_text='постепенно' is_correct=0 pos=1"
echo "  INSERT choice_text='сначала' is_correct=0 pos=2"
echo "  INSERT choice_text='раньше' is_correct=0 pos=3"
if [[ "$APPLY" -eq 1 ]]; then
  sqlite3 "$DB" "DELETE FROM vocab_choices WHERE item_id=3960;"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3960, 'обычно', 1, 0);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3960, 'постепенно', 0, 1);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3960, 'сначала', 0, 2);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3960, 'раньше', 0, 3);"
  echo "  APPLIED id=3960"
fi

echo "--- id=10017 novamente -> снова ---"
echo "  DELETE 6 existing choices"
echo "  INSERT choice_text='снова' is_correct=1 pos=0"
echo "  INSERT choice_text='сразу' is_correct=0 pos=1"
echo "  INSERT choice_text='впервые' is_correct=0 pos=2"
echo "  INSERT choice_text='вдруг' is_correct=0 pos=3"
if [[ "$APPLY" -eq 1 ]]; then
  sqlite3 "$DB" "DELETE FROM vocab_choices WHERE item_id=10017;"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10017, 'снова', 1, 0);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10017, 'сразу', 0, 1);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10017, 'впервые', 0, 2);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10017, 'вдруг', 0, 3);"
  echo "  APPLIED id=10017"
fi

echo "--- id=3963 principalmente -> главным образом ---"
echo "  DELETE 6 existing choices"
echo "  INSERT choice_text='главным образом' is_correct=1 pos=0"
echo "  INSERT choice_text='всё-таки' is_correct=0 pos=1"
echo "  INSERT choice_text='совсем' is_correct=0 pos=2"
echo "  INSERT choice_text='тоже' is_correct=0 pos=3"
if [[ "$APPLY" -eq 1 ]]; then
  sqlite3 "$DB" "DELETE FROM vocab_choices WHERE item_id=3963;"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3963, 'главным образом', 1, 0);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3963, 'всё-таки', 0, 1);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3963, 'совсем', 0, 2);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3963, 'тоже', 0, 3);"
  echo "  APPLIED id=3963"
fi

echo "--- id=10019 exatamente -> точно ---"
echo "  DELETE 6 existing choices"
echo "  INSERT choice_text='точно' is_correct=1 pos=0"
echo "  INSERT choice_text='слегка' is_correct=0 pos=1"
echo "  INSERT choice_text='немного' is_correct=0 pos=2"
echo "  INSERT choice_text='едва' is_correct=0 pos=3"
if [[ "$APPLY" -eq 1 ]]; then
  sqlite3 "$DB" "DELETE FROM vocab_choices WHERE item_id=10019;"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10019, 'точно', 1, 0);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10019, 'слегка', 0, 1);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10019, 'немного', 0, 2);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10019, 'едва', 0, 3);"
  echo "  APPLIED id=10019"
fi

echo "--- id=3970 facilmente -> легко ---"
echo "  DELETE 6 existing choices"
echo "  INSERT choice_text='легко' is_correct=1 pos=0"
echo "  INSERT choice_text='трудно' is_correct=0 pos=1"
echo "  INSERT choice_text='тихо' is_correct=0 pos=2"
echo "  INSERT choice_text='крепко' is_correct=0 pos=3"
if [[ "$APPLY" -eq 1 ]]; then
  sqlite3 "$DB" "DELETE FROM vocab_choices WHERE item_id=3970;"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3970, 'легко', 1, 0);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3970, 'трудно', 0, 1);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3970, 'тихо', 0, 2);"
  sqlite3 "$DB" "INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (3970, 'крепко', 0, 3);"
  echo "  APPLIED id=3970"
fi

if [[ "$APPLY" -eq 1 ]]; then
  echo "APPLY COMPLETE — all 6 items rebuilt"
else
  echo "DRY-RUN COMPLETE — no changes made"
fi
