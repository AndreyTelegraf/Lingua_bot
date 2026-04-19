# Adverb 5K Rebuild — Go/No-Go for Activation Prep

**Date:** 2026-04-19
**Based on:** Apply workstream (commit: see below) + live atomic validation

---

## Decision

**GO_FOR_ADVERB_5K_ACTIVATION_PREP**

**Confidence:** HIGH

---

## Basis

All four pre-conditions for activation prep are now met:

1. **Distractor rebuild applied atomically.**
   All 6 inactive 5K adverb items now have exactly 4 choices (1 CA + 3 distractors).
   Applied inside a single SQLite transaction. 0 errors.

2. **Live atomic validation: 6/6 PASS.**
   All 9 checks clear for every item in the group simultaneously:
   - item_still_inactive ✓
   - exactly_4_choices ✓
   - exactly_1_correct ✓
   - correct_answer_unchanged ✓
   - rule_1b_pass ✓ (no distractor is an active CA)
   - rule_1a_pass ✓ (no item CA is an active distractor)
   - no_cross_group_distractor ✓
   - manifest_exact_match ✓
   - no_mutual_collision ✓

3. **Active bank untouched.** No active items were modified. No is_active changes.

4. **No selector or runtime changes.**

---

## What This Decision Does NOT Authorize

- DO NOT activate any item in the next workstream.
- DO NOT skip the Stage A gloss audit.
- DO NOT open the 10K adverb group in the next workstream.
- DO NOT touch noun/10K or verb/10K active tracks.

---

## Minimum Path Forward

1. **(Next workstream)** Stage A gloss audit on the 6 rebuilt items.
2. **(After gloss audit)** Activation tranche (standard 4-stage gate).
3. **(Tranche 2, deferred)** Distractor rebuild + tranche for the 5 inactive 10K adverbs.

---

## Exact Next Prompt for Next Session

Run the next bounded workstream:
**ADVERB 5K GROUP — STAGE A GLOSS AUDIT**

Context:
- Adverb 5K distractor rebuild applied and live-validated (commit: see COMMIT SHA below)
- 6 inactive 5K adverb items are the target:
    id=3958  frequentemente  -> часто
    id=3960  geralmente      -> обычно
    id=10017 novamente       -> снова
    id=3963  principalmente  -> главным образом
    id=10019 exatamente      -> точно
    id=3970  facilmente      -> легко
- Each item now has exactly 4 choices (1 correct + 3 distractors)
- Live validation artifact: diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_live_validation.json

Mission:
Perform a Stage A gloss audit on all 6 items:
  1. Verify the Portuguese lemma is the canonical form (not inflected, not a phrase)
  2. Verify the Russian correct_answer is the canonical adverb (not archaic, not register-inappropriate)
  3. Verify no cognate transparency between Portuguese lemma and Russian CA
  4. Verify the 3 distractors are plausibly confusable Russian adverbs (not obviously wrong, not trivially eliminated)
  5. Verify no distractor is cognate-transparent with the Portuguese lemma
  6. Produce a PASS / HOLD / REJECT verdict per item with explicit reason codes
  7. Produce a group-level verdict: all-PASS required before proceeding to activation

Execution mode:
- read-only audit (no DB writes, no activation)
- narrow scope: these 6 items only
- no noun/10K or verb/10K changes

Required outputs:
  diagnostics_exports/adverb_5k_gloss_audit/current/adverb_5k_gloss_audit.json
  diagnostics_exports/adverb_5k_gloss_audit/current/adverb_5k_gloss_audit_summary.md
  diagnostics_exports/adverb_5k_gloss_audit/current/adverb_5k_gloss_audit_operator_summary.md

Git:
  commit: "vocab: stage A gloss audit for adverb 5K group"
  push to main

---

## Artifact Paths

- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_group.json`
- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_proposals.json`
- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_proposals.csv`
- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_validation.json`
- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_preapply_audit.md`
- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_apply_summary.md`
- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_live_validation.json`
- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_live_validation.md`
- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_go_nogo.md`
- `scripts/adverb_5k_rebuild_preapply_audit.py`
- `scripts/adverb_5k_rebuild_live_validate.py`
- `scripts/adverb_5k_rebuild_apply_DONOTRUN.sh` (updated: single-transaction version)
