# Adverb 5K Rebuild — Operator Summary

## Status: PREPARE-ONLY — NO DB WRITES PERFORMED

## Workstream

Distractor rebuild for 6 inactive 5K Portuguese adverb items.
All 6 items form an atomic group — partial apply is not valid.

## Validation

- Stage 1 (group extraction): PASS — 6 items confirmed
- Stage 2 (proposals): PASS — 18 new distractors proposed, all unique
- Stage 3 (group validation): PASS — all 6 items pass all 7 checks

## Proposed Changes

| item_id | lemma | CA | new distractors |
|---------|-------|----|-----------------|
| 3958 | frequentemente | часто | редко, иногда, давно |
| 3960 | geralmente | обычно | постепенно, сначала, раньше |
| 10017 | novamente | снова | сразу, впервые, вдруг |
| 3963 | principalmente | главным образом | всё-таки, совсем, тоже |
| 10019 | exatamente | точно | слегка, немного, едва |
| 3970 | facilmente | легко | трудно, тихо, крепко |

## Apply Pack

- Manifest: `diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_manifest.json`
- Apply script: `scripts/adverb_5k_rebuild_apply_DONOTRUN.sh` (dry-run by default, pass `--apply` to execute)
- Items: 6
- DELETEs: 36 (6 existing choices per item)
- INSERTs: 24 (4 per item: 1 CA + 3 distractors)

## What This Workstream Does NOT Authorize

- DO NOT activate any adverb item
- DO NOT run apply script without operator review
- DO NOT modify correct_answers or lemmas
- DO NOT open the 10K adverb group

## Next Step

1. Operator reviews this summary and the manifest.
2. Run apply workstream (separate session): `bash scripts/adverb_5k_rebuild_apply_DONOTRUN.sh data/lingua_staging.db --apply`
3. Run Stage A gloss audit on rebuilt items.
4. Activation tranche (standard 4-stage gate).
