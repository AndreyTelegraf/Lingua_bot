#!/bin/bash
# post_apply_checks.sh
# Post-apply verification for noun/10K wave 1 (49 items)
# Run after apply_staging_microbatch.sh --apply
# Run from project root

set -euo pipefail

DB="data/lingua_staging.db"
PASS=0
FAIL=0

check() {
  local label="$1"
  local actual="$2"
  local expected="$3"
  if [[ "$actual" == "$expected" ]]; then
    echo "PASS  $label: $actual"
    PASS=$((PASS + 1))
  else
    echo "FAIL  $label: got $actual, expected $expected"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== POST-APPLY CHECKS: noun/10K wave 1 ==="
echo "DB: $DB"
echo ""

# 1. Item count
V=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE topic_tag='build:noun_10k_wave1';")
check "Item count (wave1)" "$V" "49"

# 2. Choice count
V=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_choices vc JOIN vocab_items vi ON vi.id=vc.item_id WHERE vi.topic_tag='build:noun_10k_wave1';")
check "Choice count (wave1)" "$V" "196"

# 3. All items inactive
V=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE topic_tag='build:noun_10k_wave1' AND is_active=1;")
check "Active items (must be 0)" "$V" "0"

# 4. All items have exactly 4 choices
V=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items vi WHERE vi.topic_tag='build:noun_10k_wave1' AND (SELECT COUNT(*) FROM vocab_choices WHERE item_id=vi.id) != 4;")
check "Items with != 4 choices (must be 0)" "$V" "0"

# 5. All items have exactly 1 correct choice
V=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items vi WHERE vi.topic_tag='build:noun_10k_wave1' AND (SELECT COUNT(*) FROM vocab_choices WHERE item_id=vi.id AND is_correct=1) != 1;")
check "Items with != 1 correct choice (must be 0)" "$V" "0"

# 6. No duplicate lemmas in active noun/10K
V=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM (
  SELECT lemma FROM vocab_items
  WHERE pos='noun' AND bin_name='10K' AND is_active=1
  GROUP BY lemma HAVING COUNT(*) > 1
);")
check "Duplicate active noun/10K lemmas (must be 0)" "$V" "0"

# 7. Anti-collision Rule 1a: no wave1 correct_answer is an active distractor
V=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM vocab_choices vc
JOIN vocab_items vi_active ON vi_active.id=vc.item_id
JOIN vocab_items vi_wave ON vi_wave.topic_tag='build:noun_10k_wave1'
WHERE vi_active.is_active=1
  AND vc.is_correct=0
  AND vc.choice_text=vi_wave.correct_answer;")
check "Rule 1a violations: wave1 CA in active distractors (must be 0)" "$V" "0"

# 8. Anti-collision Rule 1b: no active correct_answer is a wave1 distractor
V=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM vocab_choices vc_wave
JOIN vocab_items vi_wave ON vi_wave.id=vc_wave.item_id
JOIN vocab_items vi_active ON vi_active.is_active=1
  AND vi_active.correct_answer=vc_wave.choice_text
WHERE vi_wave.topic_tag='build:noun_10k_wave1'
  AND vc_wave.is_correct=0;")
check "Rule 1b violations: active CA in wave1 distractors (must be 0)" "$V" "0"

# 9. All wave1 items have pos=noun, bin_name=10K
V=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE topic_tag='build:noun_10k_wave1' AND (pos!='noun' OR bin_name!='10K');")
check "Items with wrong pos/bin_name (must be 0)" "$V" "0"

# 10. All wave1 items have correct_answer matching choice_text where is_correct=1
V=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM vocab_items vi
JOIN vocab_choices vc ON vc.item_id=vi.id AND vc.is_correct=1
WHERE vi.topic_tag='build:noun_10k_wave1'
  AND vi.correct_answer != vc.choice_text;")
check "Correct_answer/choice mismatch (must be 0)" "$V" "0"

# 11. No duplicate choice_text within any single wave1 item
V=$(sqlite3 "$DB" "
SELECT COUNT(*) FROM (
  SELECT item_id FROM vocab_choices vc
  JOIN vocab_items vi ON vi.id=vc.item_id
  WHERE vi.topic_tag='build:noun_10k_wave1'
  GROUP BY item_id, choice_text HAVING COUNT(*) > 1
);")
check "Duplicate choice_text within item (must be 0)" "$V" "0"

# 12. Noun/10K active count after wave (should still be 1 — travesseiro only)
V=$(sqlite3 "$DB" "SELECT COUNT(*) FROM vocab_items WHERE pos='noun' AND bin_name='10K' AND is_active=1;")
check "Active noun/10K count (must be 1 — travesseiro only)" "$V" "1"

echo ""
echo "--- Summary ---"
echo "PASS: $PASS"
echo "FAIL: $FAIL"

if [[ $FAIL -eq 0 ]]; then
  echo ""
  echo "ALL CHECKS PASSED."
  echo ""
  echo "Next steps:"
  echo "  1. Submit approved.csv + import_prep_summary.json to ChatGPT for activation review."
  echo "  2. ChatGPT approves activation plan."
  echo "  3. Human activates items selectively:"
  echo "     UPDATE vocab_items SET is_active=1 WHERE id=<id>;"
  echo "     Observe cluster caps: birds max 2/session, seafood max 2/session, grains max 1/session."
  echo "  4. Run contract smoke: python scripts/runtime_vocab_smoke.py"
  echo "  5. Run selector QA to verify cluster caps are enforced."
  echo "  6. Monitor vocab_answers for learner performance signal."
else
  echo ""
  echo "CHECKS FAILED ($FAIL failures). Do not activate. Investigate before proceeding."
  exit 1
fi
