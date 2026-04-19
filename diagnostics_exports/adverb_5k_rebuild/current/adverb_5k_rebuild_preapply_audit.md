# Adverb 5K Rebuild — Pre-Apply Safety Audit

## Result

**SAFE TO PROCEED: YES**

## Checks

| Check | Result | Detail |
|-------|--------|--------|
| manifest_exists | ✓ PASS | diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_manifest.json |
| validation_exists | ✓ PASS | diagnostics_exports/adverb_5k_rebuild/current/adverb_5k_rebuild_validation.json |
| apply_script_exists | ✓ PASS | scripts/adverb_5k_rebuild_apply_DONOTRUN.sh |
| db_exists | ✓ PASS | data/lingua_staging.db |
| db_path_matches_manifest | ✓ PASS | manifest.db='data/lingua_staging.db', arg.db='data/lingua_staging.db' |
| stage3_accepted | ✓ PASS | stage3_accept=True |
| manifest_ids_match_expected | ✓ PASS | manifest=[3958, 3960, 3963, 3970, 10017, 10019], expected=[3958, 3960, 3963, 3970, 10017, 10019] |
| live_db_item_state | ✓ PASS | all 6 items confirmed pos=adverb, bin=5K, is_active=0 |
| script_only_touches_vocab_choices | ✓ PASS | tables in SQL: [] |
| script_item_ids_match_expected | ✓ PASS | script=[3958, 3960, 3963, 3970, 10017, 10019], expected=[3958, 3960, 3963, 3970, 10017, 10019] |
| no_is_active_writes | ✓ PASS | no is_active assignments found |
| no_forbidden_patterns | ✓ PASS | no forbidden patterns |
| manifest_counts_correct | ✓ PASS | deletes=36 (expected 36), inserts=24 (expected 24) |

## Live DB Item State

| item_id | lemma | bin | pos | is_active |
|---------|-------|-----|-----|-----------|
| 3958 | frequentemente | 5K | adverb | 0 |
| 3960 | geralmente | 5K | adverb | 0 |
| 3963 | principalmente | 5K | adverb | 0 |
| 3970 | facilmente | 5K | adverb | 0 |
| 10017 | novamente | 5K | adverb | 0 |
| 10019 | exatamente | 5K | adverb | 0 |

## Write Scope

- Table: `vocab_choices` only
- Item IDs: 3958, 3960, 10017, 3963, 10019, 3970
- No writes to `vocab_items`
- No `is_active` changes
- No selector/runtime/noun/verb mutations
