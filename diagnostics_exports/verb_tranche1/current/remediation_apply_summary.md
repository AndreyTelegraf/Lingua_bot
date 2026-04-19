# Verb Tranche1 Remediation — Apply Summary

**Date:** 2026-04-19
**DB:** data/lingua_staging.db
**Backup:** data/lingua_staging_preremedy_20260419_101828.db
**Script:** scripts/verb_tranche1_remediation_apply_DONOTRUN.sh

## Apply Result: SUCCESS

| Metric | Pre-apply | Post-apply | Delta |
|--------|-----------|------------|-------|
| vocab_items total | 9141 | 9141 | 0 |
| vocab_items active (is_active=1) | 809 | 809 | 0 |
| Target items is_active | 0 (all 9) | 0 (all 9) | 0 |

## CA Changes Applied

| item_id | lemma | old CA | new CA | verified |
|---------|-------|--------|--------|---------|
| 868 | acelerar | торопить | ускорять | ✓ |
| 921 | alterar | менять | изменять | ✓ |
| 1732 | implementar | выполнять | реализовывать | ✓ |
| 1759 | instalar | провести | устанавливать | ✓ |
| 2172 | pintar | писать | красить | ✓ |
| 3467 | aproximar | оценивать | приближать | ✓ |
| 3491 | cancelar | нарушать | отменять | ✓ |
| 3509 | curtir | дубить | выделывать | ✓ |
| 9328 | inventar | (kept) изобрета́ть | izобрета́ть | ✓ |

## Distractor Replacements: 38/38

All 38 distractor slots updated. Sample verified:
- acelerar (868): 5 rows updated ✓
- alterar (921): 4 rows updated ✓
- curtir (3509): 5 rows updated ✓
- inventar (9328): 4 rows updated ✓

## Safety Checks

- is_active changes: **NONE** (active count unchanged: 809)
- Forbidden tables touched: **NONE**
- Total row count drift: **0**
- Apply error: **NONE** (sqlite3 exited clean)
