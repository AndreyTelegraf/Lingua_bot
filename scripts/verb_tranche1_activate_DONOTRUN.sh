#!/usr/bin/env bash
# verb_tranche1_activate_DONOTRUN.sh
#
# PREPARE ONLY — DO NOT RUN IN THIS TASK.
# Default: DRY-RUN mode. No DB changes occur unless --apply is passed.
# This script activates 9 validated verb tranche1 items (is_active=0 → 1).
#
# Human review required before running with --apply.
# Run against staging ONLY:
#   DRY-RUN:  bash scripts/verb_tranche1_activate_DONOTRUN.sh
#   APPLY:    bash scripts/verb_tranche1_activate_DONOTRUN.sh --apply data/lingua_staging.db
#
# Prereq: sqlite3 CLI available.

set -euo pipefail

APPLY=0
DB="data/lingua_staging.db"

for arg in "$@"; do
    case "$arg" in
        --apply) APPLY=1 ;;
        data/*.db) DB="$arg" ;;
        *.db) DB="$arg" ;;
    esac
done

TARGET_IDS="(868, 921, 1732, 1759, 2172, 3467, 3491, 3509, 9328)"
EXPECTED_COUNT=9

echo "=== VERB TRANCHE1 ACTIVATION SCRIPT ==="
echo "DB:   $DB"
echo "MODE: $([ "$APPLY" = "1" ] && echo "APPLY" || echo "DRY-RUN")"
echo ""

# ============================================================
# PRE-ACTIVATION CHECKS (read-only, always run)
# ============================================================

echo "--- Pre-activation checks ---"

ITEM_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE id IN $TARGET_IDS;")
echo "  [1] Item existence: $ITEM_COUNT / $EXPECTED_COUNT"
if [ "$ITEM_COUNT" -ne "$EXPECTED_COUNT" ]; then
    echo "  FAIL: expected $EXPECTED_COUNT items, found $ITEM_COUNT"
    exit 1
fi

INACTIVE_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE id IN $TARGET_IDS AND is_active=0;")
echo "  [2] All items is_active=0: $INACTIVE_COUNT / $EXPECTED_COUNT"
if [ "$INACTIVE_COUNT" -ne "$EXPECTED_COUNT" ]; then
    echo "  FAIL: $((EXPECTED_COUNT - INACTIVE_COUNT)) items already active (expected all inactive)"
    exit 1
fi

POS_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE id IN $TARGET_IDS AND pos='verb';")
echo "  [3] All items pos=verb: $POS_COUNT / $EXPECTED_COUNT"
if [ "$POS_COUNT" -ne "$EXPECTED_COUNT" ]; then
    echo "  FAIL: $((EXPECTED_COUNT - POS_COUNT)) items not pos=verb"
    exit 1
fi

DUP_LEMMA=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM vocab_items vi
WHERE vi.id IN $TARGET_IDS
  AND EXISTS (
    SELECT 1 FROM vocab_items active
    WHERE active.lemma = vi.lemma
      AND active.is_active = 1
      AND active.id != vi.id
  );
")
echo "  [4] No duplicate lemmas vs active bank: $DUP_LEMMA duplicates found"
if [ "$DUP_LEMMA" -ne "0" ]; then
    echo "  FAIL: $DUP_LEMMA duplicate lemmas found"
    exit 1
fi

R1A_FAIL=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM vocab_items vi
WHERE vi.id IN $TARGET_IDS
  AND vi.correct_answer IN (
    SELECT DISTINCT vc.choice_text FROM vocab_choices vc
    JOIN vocab_items active ON active.id = vc.item_id
    WHERE active.is_active = 1 AND vc.is_correct = 0
  );
")
echo "  [5] Rule 1a (CA not in active distractors): $R1A_FAIL failures"
if [ "$R1A_FAIL" -ne "0" ]; then
    echo "  FAIL: $R1A_FAIL items fail Rule 1a"
    exit 1
fi

R1B_FAIL=$(sqlite3 "$DB" "
SELECT COUNT(DISTINCT vc.item_id) FROM vocab_choices vc
JOIN vocab_items vi ON vi.id = vc.item_id
WHERE vi.id IN $TARGET_IDS
  AND vc.is_correct = 0
  AND vc.choice_text IN (
    SELECT correct_answer FROM vocab_items WHERE is_active = 1 AND correct_answer IS NOT NULL
  );
")
echo "  [6] Rule 1b (no distractor is active CA): $R1B_FAIL items with violations"
if [ "$R1B_FAIL" -ne "0" ]; then
    echo "  FAIL: $R1B_FAIL items fail Rule 1b"
    exit 1
fi

CHOICE_INTEGRITY=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM (
  SELECT vi.id, COUNT(CASE WHEN vc.is_correct=1 THEN 1 END) as correct_ct
  FROM vocab_items vi
  JOIN vocab_choices vc ON vc.item_id = vi.id
  WHERE vi.id IN $TARGET_IDS
  GROUP BY vi.id
  HAVING correct_ct != 1
);
")
echo "  [7] Choice integrity (exactly 1 correct choice per item): $CHOICE_INTEGRITY violations"
if [ "$CHOICE_INTEGRITY" -ne "0" ]; then
    echo "  FAIL: $CHOICE_INTEGRITY items have incorrect choice counts"
    exit 1
fi

echo ""
echo "All pre-activation checks PASSED."
echo ""

# ============================================================
# VERB COUNT SUMMARY (before)
# ============================================================

VERB_ACTIVE_BEFORE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='verb';")
VERB_10K_BEFORE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='verb' AND bin_name='10K';")
echo "--- Current verb coverage ---"
echo "  Active verbs (all bins): $VERB_ACTIVE_BEFORE"
echo "  Active verbs (10K):      $VERB_10K_BEFORE"
echo ""

# ============================================================
# ACTIVATION (only if --apply passed)
# ============================================================

if [ "$APPLY" = "0" ]; then
    echo "=== DRY-RUN COMPLETE — no DB changes made ==="
    echo "Projected after activation:"
    echo "  Active verbs (all bins): $((VERB_ACTIVE_BEFORE + EXPECTED_COUNT))"
    echo "  Active verbs (10K):      $((VERB_10K_BEFORE + EXPECTED_COUNT))"
    echo ""
    echo "To apply: bash scripts/verb_tranche1_activate_DONOTRUN.sh --apply data/lingua_staging.db"
    exit 0
fi

echo "--- Applying activation ---"
sqlite3 "$DB" <<'SQL'
BEGIN TRANSACTION;
UPDATE vocab_items SET is_active = 1
WHERE id IN (868, 921, 1732, 1759, 2172, 3467, 3491, 3509, 9328)
  AND is_active = 0;
COMMIT;
SQL

ROWS_CHANGED=$(sqlite3 "$DB" "SELECT changes();")
echo "  Rows updated: $ROWS_CHANGED"

# Post-activation verb count
VERB_ACTIVE_AFTER=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='verb';")
VERB_10K_AFTER=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE is_active=1 AND pos='verb' AND bin_name='10K';")
echo ""
echo "--- Post-activation verb coverage ---"
echo "  Active verbs (all bins): $VERB_ACTIVE_BEFORE → $VERB_ACTIVE_AFTER (delta=$((VERB_ACTIVE_AFTER - VERB_ACTIVE_BEFORE)))"
echo "  Active verbs (10K):      $VERB_10K_BEFORE → $VERB_10K_AFTER (delta=$((VERB_10K_AFTER - VERB_10K_BEFORE)))"

# Verify
NEWLY_ACTIVE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE id IN (868, 921, 1732, 1759, 2172, 3467, 3491, 3509, 9328) AND is_active=1;")
echo ""
echo "  Post-activation is_active=1 check: $NEWLY_ACTIVE / $EXPECTED_COUNT"
if [ "$NEWLY_ACTIVE" -ne "$EXPECTED_COUNT" ]; then
    echo "  WARN: only $NEWLY_ACTIVE of $EXPECTED_COUNT items now active"
fi

echo ""
echo "=== ACTIVATION COMPLETE ==="
echo "Run post-activation collision check:"
echo "  python3 scripts/verb_tranche1_target_reconfirm.py --db $DB"
