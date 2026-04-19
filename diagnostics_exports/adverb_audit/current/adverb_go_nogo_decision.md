# Adverb Readiness — Go/No-Go Decision

**Date:** 2026-04-19
**Based on:** Stage 1 (state audit) + Stage 2 (usability review)

---

## Decision

**BOUNDED_ADVERB_TRANCHE_PATH_EXISTS**

**Confidence:** HIGH

---

## Exact Reason

The adverb inventory contains 6 inactive 5K items whose Portuguese lemmas and Russian
correct_answers are structurally valid and do not conflict with the currently active bank.
The blockers are mechanical distractor issues only, not content or inventory gaps.

Specifically:

1. **The lemmas and glosses exist and are valid.**
   Six inactive 5K items (frequentemente, geralmente, novamente, principalmente, exatamente,
   facilmente) have correct Russian translations, no cognate transparency risk, and no
   duplicate lemma in the active bank.

2. **The only blockers are cross-group distractor references.**
   Every one of these items was designed with distractors drawn from the correct_answers of
   other inactive adverbs. No distractor is currently an active correct_answer, but activating
   any item would make its CA an active CA, which would then trigger Rule 1b violations in
   peer items that use it as a distractor. This is a structural cluster design, not a content
   quality failure.

3. **The fix is bounded and well-defined.**
   Replacing the 5 distractors per item with bank-safe Russian adverbs (not in any active CA
   set, not in any active distractor set, not cross-referencing each other) unblocks the
   entire 5K group. No new vocab pairs need to be generated. The lemmas and CAs stay
   unchanged.

4. **The 10K group (5 items) is also recoverable via the same mechanism.**
   All 5 inactive 10K adverbs (seriamente, simplesmente, realmente, totalmente, parcialmente)
   fail Rule 1b only because `медленно` appears in each item's distractor set and `медленно`
   is the correct_answer for the active item `devagar`. A distractor rebuild removes this
   blocker. These 5 items form a second bounded workstream after the 5K group.

5. **No fresh Portuguese-Russian candidate generation is required.**
   The inventory is sufficient: 6 5K items + 5 10K items = 11 items for a first tranche,
   comparable in size to verb tranche1 (9 items).

---

## Why FRESH_ADVERB_GENERATION_REQUIRED Is Deferred

Fresh generation would be needed if:
- The existing vocab pairs (lemma → correct_answer) were invalid or too thin
- The content quality were too low to pass a gloss audit
- The pool size were insufficient to form any tranche

None of these conditions hold:
- All 6 usable-path items have non-cognate Russian translations
- Bin coverage (5K + 10K) matches the activation pattern used for verbs
- 11 items total is a viable first tranche size

Fresh generation remains the fallback if the distractor rebuild reveals hidden content
quality issues during the subsequent Stage A gloss audit.

---

## Minimum Path to First Adverb Tranche

1. **Distractor rebuild workstream** — 5K group (6 items): replace all 5 distractors per item
   with bank-safe Russian adverbs. This is the immediate next step.
2. **Stage A gloss audit** on rebuilt items.
3. **Activation tranche** for items that pass gloss audit.
4. *(Optional, tranche 2)* Distractor rebuild for 10K group (5 items), then same path.

---

## What This Decision Does NOT Authorize

- Do not activate anything now.
- Do not run the distractor rebuild in this workstream.
- Do not modify the active bank (no noun/10K or active verb changes).
- Do not open the 10K group until the 5K group tranche is complete and in monitoring.
