#!/usr/bin/env bash
# =============================================================================
# DO NOT RUN — PREPARE ONLY
# adverb_5k_activate_DONOTRUN.sh
#
# Activation script for the 6-item adverb 5K group.
# This script defaults to DRY-RUN mode and will NOT activate any items
# unless explicitly invoked with --execute flag.
#
# DO NOT run this script until a separate activation workstream is initiated
# and all go/no-go checks have been re-confirmed live.
# =============================================================================

set -euo pipefail

DB_PATH="${DB_PATH:-data/lingua_staging.db}"
EXECUTE=0

if [[ "${1:-}" == "--execute" ]]; then
  EXECUTE=1
fi

TARGET_IDS=(3958 3960 10017 3963 10019 3970)
TARGET_LEMMAS=(frequentemente geralmente novamente principalmente exatamente facilmente)
TARGET_CAS=("часто" "обычно" "снова" "главным образом" "точно" "легко")

echo "============================================================"
echo "ADVERB 5K ACTIVATION SCRIPT"
echo "Mode: $([ $EXECUTE -eq 1 ] && echo 'EXECUTE' || echo 'DRY-RUN (default)')"
echo "DB: $DB_PATH"
echo "============================================================"
echo ""

if [ $EXECUTE -eq 0 ]; then
  echo "[DRY-RUN] No activation will be performed."
  echo ""
fi

FAIL=0

# --- Pre-flight checks ---
echo "--- PRE-FLIGHT CHECKS ---"
echo ""

for i in "${!TARGET_IDS[@]}"; do
  IID="${TARGET_IDS[$i]}"
  LEMMA="${TARGET_LEMMAS[$i]}"
  CA="${TARGET_CAS[$i]}"

  echo "Checking item_id=$IID ($LEMMA)..."

  # 1. Item existence check
  EXISTS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM vocab_items WHERE id=$IID;")
  if [ "$EXISTS" -ne 1 ]; then
    echo "  [FAIL] item_id=$IID: NOT FOUND in DB"
    FAIL=1
    continue
  fi
  echo "  [OK] exists"

  # 2. is_active=0 check
  IS_ACTIVE=$(sqlite3 "$DB_PATH" "SELECT is_active FROM vocab_items WHERE id=$IID;")
  if [ "$IS_ACTIVE" -ne 0 ]; then
    echo "  [FAIL] item_id=$IID: is_active=$IS_ACTIVE (expected 0)"
    FAIL=1
  else
    echo "  [OK] is_active=0"
  fi

  # 3. pos=adverb check
  POS=$(sqlite3 "$DB_PATH" "SELECT pos FROM vocab_items WHERE id=$IID;")
  if [ "$POS" != "adverb" ]; then
    echo "  [FAIL] item_id=$IID: pos=$POS (expected adverb)"
    FAIL=1
  else
    echo "  [OK] pos=adverb"
  fi

  # 4. bin_name=5K check
  BIN=$(sqlite3 "$DB_PATH" "SELECT bin_name FROM vocab_items WHERE id=$IID;")
  if [ "$BIN" != "5K" ]; then
    echo "  [FAIL] item_id=$IID: bin_name=$BIN (expected 5K)"
    FAIL=1
  else
    echo "  [OK] bin_name=5K"
  fi

  # 5. correct_answer check
  CA_DB=$(sqlite3 "$DB_PATH" "SELECT correct_answer FROM vocab_items WHERE id=$IID;")
  if [ "$CA_DB" != "$CA" ]; then
    echo "  [FAIL] item_id=$IID: correct_answer='$CA_DB' (expected '$CA')"
    FAIL=1
  else
    echo "  [OK] correct_answer='$CA'"
  fi

  # 6. Exactly 4 choices
  N_CHOICES=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM vocab_choices WHERE item_id=$IID;")
  if [ "$N_CHOICES" -ne 4 ]; then
    echo "  [FAIL] item_id=$IID: $N_CHOICES choices (expected 4)"
    FAIL=1
  else
    echo "  [OK] 4 choices"
  fi

  # 7. Exactly 1 correct choice
  N_CORRECT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM vocab_choices WHERE item_id=$IID AND is_correct=1;")
  if [ "$N_CORRECT" -ne 1 ]; then
    echo "  [FAIL] item_id=$IID: $N_CORRECT correct choices (expected 1)"
    FAIL=1
  else
    echo "  [OK] 1 correct choice"
  fi

  # 8. Rule 1a: my CA not in other group items' distractors
  for j in "${!TARGET_IDS[@]}"; do
    OID="${TARGET_IDS[$j]}"
    if [ "$OID" -eq "$IID" ]; then continue; fi
    IN_OD=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM vocab_choices WHERE item_id=$OID AND is_correct=0 AND choice_text='$CA';")
    if [ "$IN_OD" -gt 0 ]; then
      echo "  [FAIL] Rule 1a: CA '$CA' appears as distractor in item_id=$OID"
      FAIL=1
    fi
  done
  echo "  [OK] Rule 1a"

  # 9. Rule 1b: my distractors not equal to another item's CA
  RULE_1B_FAIL=0
  for j in "${!TARGET_IDS[@]}"; do
    OID="${TARGET_IDS[$j]}"
    if [ "$OID" -eq "$IID" ]; then continue; fi
    OCA="${TARGET_CAS[$j]}"
    IN_MY=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM vocab_choices WHERE item_id=$IID AND is_correct=0 AND choice_text='$OCA';")
    if [ "$IN_MY" -gt 0 ]; then
      echo "  [FAIL] Rule 1b: distractor '$OCA' (CA of item $OID) appears in my distractors"
      FAIL=1
      RULE_1B_FAIL=1
    fi
  done
  if [ $RULE_1B_FAIL -eq 0 ]; then
    echo "  [OK] Rule 1b"
  fi

  # 10. Group atomic consistency: none of group CAs appear as my distractors
  GA_FAIL=0
  for j in "${!TARGET_IDS[@]}"; do
    OCA="${TARGET_CAS[$j]}"
    IN_MY=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM vocab_choices WHERE item_id=$IID AND is_correct=0 AND choice_text='$OCA';")
    if [ "$IN_MY" -gt 0 ]; then
      echo "  [FAIL] Group atomic: group CA '$OCA' appears as distractor in item_id=$IID"
      FAIL=1
      GA_FAIL=1
    fi
  done
  if [ $GA_FAIL -eq 0 ]; then
    echo "  [OK] Group atomic consistency"
  fi

  # 11. Duplicate lemma vs active bank
  DUP=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM vocab_items WHERE lemma='$LEMMA' AND is_active=1 AND id!=$IID;")
  if [ "$DUP" -gt 0 ]; then
    echo "  [FAIL] Duplicate lemma: '$LEMMA' has $DUP active entries in DB"
    FAIL=1
  else
    echo "  [OK] No duplicate active lemma"
  fi

  echo ""
done

# --- Row count check ---
echo "--- ACTIVATION ROW COUNT CHECK ---"
ADVERB_ACTIVE_BEFORE=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='adverb';")
echo "Current active adverbs: $ADVERB_ACTIVE_BEFORE"
echo "Items to activate: ${#TARGET_IDS[@]}"
ADVERB_ACTIVE_AFTER=$((ADVERB_ACTIVE_BEFORE + ${#TARGET_IDS[@]}))
echo "Expected after activation: $ADVERB_ACTIVE_AFTER"
echo ""

# --- Summary ---
if [ $FAIL -ne 0 ]; then
  echo "============================================================"
  echo "PRE-FLIGHT FAILED — activation aborted"
  echo "Resolve all FAIL items before attempting activation."
  echo "============================================================"
  exit 1
fi

echo "============================================================"
echo "ALL PRE-FLIGHT CHECKS PASSED"
echo "============================================================"
echo ""

if [ $EXECUTE -eq 0 ]; then
  echo "[DRY-RUN] Activation NOT performed."
  echo "Re-run with --execute flag in the activation workstream to activate."
  echo ""
  echo "Post-activation adverb count summary (projected):"
  echo "  Active adverbs before: $ADVERB_ACTIVE_BEFORE"
  echo "  Items to activate:     ${#TARGET_IDS[@]}"
  echo "  Active adverbs after:  $ADVERB_ACTIVE_AFTER"
  exit 0
fi

# =============================================================================
# EXECUTE MODE — only reachable with --execute flag
# =============================================================================
echo "[EXECUTE] Activating ${#TARGET_IDS[@]} items..."
echo ""

for IID in "${TARGET_IDS[@]}"; do
  sqlite3 "$DB_PATH" "UPDATE vocab_items SET is_active=1, updated_at=CURRENT_TIMESTAMP WHERE id=$IID;"
  ACTIVE_NOW=$(sqlite3 "$DB_PATH" "SELECT is_active FROM vocab_items WHERE id=$IID;")
  echo "  item_id=$IID: is_active=$ACTIVE_NOW"
done

echo ""
echo "--- POST-ACTIVATION ADVERB COUNT SUMMARY ---"
ADVERB_ACTIVE_NOW=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='adverb';")
echo "  Active adverbs after:  $ADVERB_ACTIVE_NOW"
ALL_5K_ADVERB=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='adverb' AND bin_name='5K';")
echo "  Active 5K adverbs:     $ALL_5K_ADVERB"
echo ""
echo "============================================================"
echo "ACTIVATION COMPLETE"
echo "============================================================"
