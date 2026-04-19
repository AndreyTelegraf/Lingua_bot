# Verb Tranche1 — Activation Apply Summary

**Date:** 2026-04-19
**DB:** data/lingua_staging.db
**Backup:** data/lingua_staging_preactivation_20260419_103602.db
**Script:** scripts/verb_tranche1_activate_DONOTRUN.sh --apply

## Apply Result: SUCCESS

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total active items | 809 | 818 | +9 |
| Active verbs (all bins) | 176 | 185 | +9 |
| Active verbs (10K) | 41 | 50 | +9 |
| Active noun/10K | 13 | 13 | 0 |
| Active adverbs | 40 | 40 | 0 |

## Activated Items (confirmed is_active=1)

| item_id | lemma | CA | bin |
|---------|-------|----|-----|
| 868 | acelerar | ускорять | 10K |
| 921 | alterar | изменять | 10K |
| 1732 | implementar | реализовывать | 10K |
| 1759 | instalar | устанавливать | 10K |
| 2172 | pintar | красить | 10K |
| 3467 | aproximar | приближать | 10K |
| 3491 | cancelar | отменять | 10K |
| 3509 | curtir | выделывать | 10K |
| 9328 | inventar | изобрета́ть | 10K |

## Notes

- Script pre-activation checks: 7/7 PASS
- `SELECT changes()` returned 0 due to separate sqlite3 connection after heredoc — this is a display artifact only. Actual row delta confirmed by post-apply count (+9).
- No noun/10K or adverb drift detected.
