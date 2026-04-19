# Adverb 5K Rebuild — Apply Summary

## Result: APPLIED SUCCESSFULLY

## Backup

| Field | Value |
|-------|-------|
| Backup path | `data/lingua_staging_backup_adverb5k_20260419_232032.db` |
| Backup size | 48 MB |

## Apply Log

Apply script executed: `bash scripts/adverb_5k_rebuild_apply_DONOTRUN.sh data/lingua_staging.db --apply`

All 6 items rebuilt inside a single SQLite transaction (`BEGIN` / `COMMIT`).
Script exited 0. No errors.

## Row Counts

| Metric | Planned | Actual | Match |
|--------|---------|--------|-------|
| DELETEs (vocab_choices) | 36 | 36 | ✓ |
| INSERTs (vocab_choices) | 24 | 24 | ✓ |
| Choices per item after | 4 | 4 | ✓ |

## Post-Apply Item State

| item_id | lemma | choices_after | is_active |
|---------|-------|---------------|-----------|
| 3958 | frequentemente | 4 | 0 |
| 3960 | geralmente | 4 | 0 |
| 10017 | novamente | 4 | 0 |
| 3963 | principalmente | 4 | 0 |
| 10019 | exatamente | 4 | 0 |
| 3970 | facilmente | 4 | 0 |

## Atomicity

All 36 DELETE + 24 INSERT statements executed within a single `BEGIN`/`COMMIT` block.
No partial-apply state possible.

## What Was NOT Changed

- No `is_active` values modified
- No `vocab_items` rows modified
- No lemmas or correct_answers changed
- No selector, runtime, noun, or verb tables touched

## Next Step

Run Stage 3 live atomic validation.
