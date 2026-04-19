# Adverb 5K Activation — Stage 2: Backup and Activate

**Date:** 2026-04-20
**Backup:** data/lingua_staging_backup_adverb5k_activate_20260420_000624.db
**Script:** scripts/adverb_5k_activate_DONOTRUN.sh --execute

---

## Activation Log

| item_id | lemma | is_active after |
|---------|-------|----------------|
| 3958 | frequentemente | 1 |
| 3960 | geralmente | 1 |
| 10017 | novamente | 1 |
| 3963 | principalmente | 1 |
| 10019 | exatamente | 1 |
| 3970 | facilmente | 1 |

Script exit: 0 (success)

---

## Count Delta

| POS | Before | After | Delta |
|-----|--------|-------|-------|
| adverb | 40 | 46 | +6 |
| noun | 397 | 397 | 0 |
| verb | 185 | 185 | 0 |
| adverb/5K | — | 16 | — |

---

## Acceptance

- Script completed without error: ✓
- Exactly 6 target items became is_active=1: ✓
- No other is_active drift (noun/verb unchanged): ✓
- Active adverb count increased by exactly 6: ✓

**Stage 2: PASS**
