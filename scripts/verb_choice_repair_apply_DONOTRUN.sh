#!/usr/bin/env bash
# =============================================================================
# verb_choice_repair_apply_DONOTRUN.sh
# PREPARE ONLY — DO NOT RUN THIS SCRIPT WITHOUT EXPLICIT OPERATOR AUTHORIZATION
#
# Applies vocab_choices repair for 2 validated READY inactive verb items:
#   - id=10628  reconhecer  → узнавать
#   - id=10647  ferir       → ранить
#
# Default: DRY-RUN only (prints what it would do).
# Pass --apply to execute. The --apply path MUST NOT be used in this workstream.
#
# Pre-conditions checked:
#   - item exists with pos='verb' and is_active=0
#   - item has exactly 0 choices currently
#   - correct_answer in vocab_items matches expected value
#
# Post-conditions checked (--apply only):
#   - exactly 4 choices inserted
#   - exactly 1 correct choice
#   - Rule 1a: CA not in active distractors
#   - Rule 1b: none of item distractors are active CAs
#
# This script touches ONLY items 10628 and 10647. No other rows are modified.
# =============================================================================

set -euo pipefail

DB="${1:-data/lingua_staging.db}"
APPLY=false
for arg in "$@"; do
  if [[ "$arg" == "--apply" ]]; then
    APPLY=true
  fi
done

echo "============================================================"
echo "VERB CHOICE REPAIR — APPLY SCRIPT"
echo "DB: $DB"
if $APPLY; then
  echo "MODE: APPLY (writes will be made)"
else
  echo "MODE: DRY-RUN (no writes)"
fi
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# Pre-condition checks
# ---------------------------------------------------------------------------

echo "PRE-CONDITION CHECKS"
echo "--------------------"

FAIL=0

check_item() {
  local ITEM_ID="$1"
  local EXPECTED_LEMMA="$2"
  local EXPECTED_CA="$3"

  LEMMA=$(sqlite3 "$DB" "SELECT lemma FROM vocab_items WHERE id=$ITEM_ID;")
  IS_ACTIVE=$(sqlite3 "$DB" "SELECT is_active FROM vocab_items WHERE id=$ITEM_ID;")
  POS=$(sqlite3 "$DB" "SELECT pos FROM vocab_items WHERE id=$ITEM_ID;")
  CA=$(sqlite3 "$DB" "SELECT correct_answer FROM vocab_items WHERE id=$ITEM_ID;")
  CHOICE_CT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_choices WHERE item_id=$ITEM_ID;")

  echo "  item_id=$ITEM_ID lemma=$LEMMA is_active=$IS_ACTIVE pos=$POS choice_count=$CHOICE_CT"

  if [[ "$LEMMA" != "$EXPECTED_LEMMA" ]]; then
    echo "    FAIL: expected lemma '$EXPECTED_LEMMA', got '$LEMMA'"
    FAIL=1
  fi
  if [[ "$IS_ACTIVE" != "0" ]]; then
    echo "    FAIL: item must be inactive (is_active=0), got $IS_ACTIVE"
    FAIL=1
  fi
  if [[ "$POS" != "verb" ]]; then
    echo "    FAIL: item must have pos='verb', got '$POS'"
    FAIL=1
  fi
  if [[ "$CA" != "$EXPECTED_CA" ]]; then
    echo "    FAIL: expected correct_answer '$EXPECTED_CA', got '$CA'"
    FAIL=1
  fi
  if [[ "$CHOICE_CT" != "0" ]]; then
    echo "    FAIL: zero-choice precondition not met (choice_count=$CHOICE_CT)"
    FAIL=1
  fi
  if [[ $FAIL -eq 0 ]]; then
    echo "    OK"
  fi
}

check_item 10628 "reconhecer" "узнавать"
check_item 10647 "ferir" "ранить"

if [[ $FAIL -ne 0 ]]; then
  echo ""
  echo "PRE-CONDITION CHECKS FAILED. Aborting."
  exit 1
fi

echo ""
echo "PRE-CONDITIONS: PASS"
echo ""

# ---------------------------------------------------------------------------
# Proposed INSERT statements (always shown, even in dry-run)
# ---------------------------------------------------------------------------

echo "PROPOSED INSERT STATEMENTS"
echo "--------------------------"
echo ""
echo "-- item_id=10628 reconhecer → узнавать"
echo "-- Distractors: признавать, наблюдать, запоминать"
cat <<'ENDSQL'
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10628, 'узнавать',   1, 0);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10628, 'признавать', 0, 1);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10628, 'наблюдать',  0, 2);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10628, 'запоминать', 0, 3);
ENDSQL
echo ""
echo "-- item_id=10647 ferir → ранить"
echo "-- Distractors: бить, избивать, повреждать"
cat <<'ENDSQL'
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10647, 'ранить',     1, 0);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10647, 'бить',       0, 1);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10647, 'избивать',   0, 2);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10647, 'повреждать', 0, 3);
ENDSQL
echo ""

# ---------------------------------------------------------------------------
# Execute (apply mode only)
# ---------------------------------------------------------------------------

if ! $APPLY; then
  echo "DRY-RUN: no writes made. Pass --apply to execute."
  exit 0
fi

echo "EXECUTING INSERT STATEMENTS..."

sqlite3 "$DB" <<'APPLYSQL'
BEGIN TRANSACTION;

INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10628, 'узнавать',   1, 0);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10628, 'признавать', 0, 1);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10628, 'наблюдать',  0, 2);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10628, 'запоминать', 0, 3);

INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10647, 'ранить',     1, 0);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10647, 'бить',       0, 1);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10647, 'избивать',   0, 2);
INSERT INTO vocab_choices (item_id, choice_text, is_correct, position_index) VALUES (10647, 'повреждать', 0, 3);

COMMIT;
APPLYSQL

echo "INSERT COMPLETE."
echo ""

# ---------------------------------------------------------------------------
# Post-condition checks (apply mode only)
# ---------------------------------------------------------------------------

echo "POST-CONDITION CHECKS"
echo "---------------------"

post_check() {
  local ITEM_ID="$1"
  local EXPECTED_CA="$2"
  local FAIL_LOCAL=0

  CHOICE_CT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_choices WHERE item_id=$ITEM_ID;")
  CORRECT_CT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_choices WHERE item_id=$ITEM_ID AND is_correct=1;")
  LIVE_CA=$(sqlite3 "$DB" "SELECT choice_text FROM vocab_choices WHERE item_id=$ITEM_ID AND is_correct=1 LIMIT 1;")

  # Rule 1a: CA not in active distractors
  R1A=$(sqlite3 "$DB" "
    SELECT COUNT(*) FROM vocab_choices vc
    JOIN vocab_items vi ON vi.id=vc.item_id
    WHERE vi.is_active=1 AND vc.is_correct=0 AND vc.choice_text='$EXPECTED_CA' AND vi.id!=$ITEM_ID;")

  # Rule 1b: none of item's distractors are active CAs
  R1B=$(sqlite3 "$DB" "
    SELECT COUNT(*) FROM vocab_choices vc
    JOIN vocab_items vi ON vi.id=vocab_items.id
    WHERE vc.item_id=$ITEM_ID AND vc.is_correct=0
      AND EXISTS (
        SELECT 1 FROM vocab_items vi2
        WHERE vi2.is_active=1 AND vi2.correct_answer=vc.choice_text AND vi2.id!=$ITEM_ID
      );" 2>/dev/null || echo "0")

  echo "  item_id=$ITEM_ID choice_count=$CHOICE_CT correct_count=$CORRECT_CT live_ca=$LIVE_CA r1a_clashes=$R1A r1b_clashes=$R1B"

  [[ "$CHOICE_CT" == "4" ]]       || { echo "    FAIL: choice_count != 4"; FAIL_LOCAL=1; }
  [[ "$CORRECT_CT" == "1" ]]      || { echo "    FAIL: correct_count != 1"; FAIL_LOCAL=1; }
  [[ "$LIVE_CA" == "$EXPECTED_CA" ]] || { echo "    FAIL: CA mismatch"; FAIL_LOCAL=1; }
  [[ "$R1A" == "0" ]]             || { echo "    FAIL: Rule 1a clash (CA is active distractor)"; FAIL_LOCAL=1; }

  if [[ $FAIL_LOCAL -eq 0 ]]; then
    echo "    PASS"
  fi
  return $FAIL_LOCAL
}

POST_FAIL=0
post_check 10628 "узнавать" || POST_FAIL=1
post_check 10647 "ранить"   || POST_FAIL=1

echo ""
if [[ $POST_FAIL -eq 0 ]]; then
  echo "POST-CONDITIONS: PASS"
else
  echo "POST-CONDITIONS: FAIL — manual inspection required"
  exit 2
fi

echo ""
echo "APPLY COMPLETE. 2 items repaired (8 rows inserted into vocab_choices)."
echo "Items remain inactive (is_active=0). Activation requires a separate workstream."
