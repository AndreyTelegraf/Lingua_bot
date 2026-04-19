# Adverb — Minimum Next Step

**Decision:** BOUNDED_ADVERB_TRANCHE_PATH_EXISTS
**Source:** adverb_go_nogo_decision.md

---

## Next Bounded Workstream

**ADVERB 5K GROUP — DISTRACTOR REBUILD PREPARE-ONLY**

### Scope

Six inactive 5K adverb items whose correct_answers are bank-safe but whose distractor
sets consist entirely of correct_answers of other inactive adverbs (cross-group cluster):

| item_id | lemma | CA |
|---------|-------|-----|
| 3958 | frequentemente | часто |
| 3960 | geralmente | обычно |
| 10017 | novamente | снова |
| 3963 | principalmente | главным образом |
| 10019 | exatamente | точно |
| 3970 | facilmente | легко |

### What the workstream must do

1. **Audit existing distractor sets** — confirm exactly which distractors in each item
   are cross-references to inactive adverb CAs (this audit was completed here; results
   are in `adverb_inventory_usability.json`).

2. **Propose replacement distractors** for each item — 5 new distractors per item that:
   - Are valid Russian adverbs (single-word preferred)
   - Are not in the active correct_answer set
   - Are not correct_answers of other items in the repair batch
   - Are not cognate-transparent
   - Maintain plausible semantic distance from the item's correct_answer

3. **Validate proposed sets** — confirm Rule 1a and Rule 1b pass for all 6 items
   simultaneously (batch validation, not item-by-item, to catch mutual conflicts).

4. **Build prepare-only apply pack** — DO NOT execute; the apply workstream is separate.

### What the workstream must NOT do

- Do not activate anything.
- Do not touch the 10K group in this workstream (it is tranche 2).
- Do not change the items' correct_answers or lemmas.
- Do not touch active items.
- Do not open noun/10K or verb monitoring scope.

### Expected outputs

- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_proposals.json`
- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_proposals.csv`
- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_validation.json`
- `scripts/adverb_5k_rebuild_apply_DONOTRUN.sh`
- `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_operator_summary.md`

### Why this is the minimum step

Activating even a single adverb from the 5K group without distractor rebuild would
create Rule 1b violations in the peer items. The rebuild must happen first and must
cover all 6 items atomically to avoid ordering-dependency bugs.

The 10K group is deferred because:
- 10K items require a more extensive rebuild (remove медленно cross-CA, rebuild 5 distractors
  per item)
- Completing 5K first gives a small monitoring baseline for adverbs before scaling

---

## After This Workstream

1. Apply distractor rebuild (separate apply workstream, gated on prepare-only review).
2. Run Stage A gloss audit on the 6 rebuilt items.
3. Activation tranche (following the standard 4-stage gate used for verb tranche1).
4. Monitor. Establish adverb T1–T4 thresholds (extend monitoring runner).
