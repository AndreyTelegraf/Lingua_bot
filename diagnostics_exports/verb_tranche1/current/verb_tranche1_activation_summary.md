# Verb Tranche1 — Activation Pack Summary

**DB:** data/lingua_staging.db
**Date:** 2026-04-19
**Status:** GREEN

## Collision Report

| item_id | lemma | bin | CA | pos | is_active | no_dup | R1a | R1b | choices | readiness |
|---------|-------|-----|----|-----|-----------|--------|-----|-----|---------|-----------|
| 868 | acelerar | 10K | ускорять | ✓ | 0✓ | ✓ | ✓ | ✓ | ✓ | ACTIVATION_READY_PREPARED |
| 921 | alterar | 10K | изменять | ✓ | 0✓ | ✓ | ✓ | ✓ | ✓ | ACTIVATION_READY_PREPARED |
| 1732 | implementar | 10K | реализовывать | ✓ | 0✓ | ✓ | ✓ | ✓ | ✓ | ACTIVATION_READY_PREPARED |
| 1759 | instalar | 10K | устанавливать | ✓ | 0✓ | ✓ | ✓ | ✓ | ✓ | ACTIVATION_READY_PREPARED |
| 2172 | pintar | 10K | красить | ✓ | 0✓ | ✓ | ✓ | ✓ | ✓ | ACTIVATION_READY_PREPARED |
| 3467 | aproximar | 10K | приближать | ✓ | 0✓ | ✓ | ✓ | ✓ | ✓ | ACTIVATION_READY_PREPARED |
| 3491 | cancelar | 10K | отменять | ✓ | 0✓ | ✓ | ✓ | ✓ | ✓ | ACTIVATION_READY_PREPARED |
| 3509 | curtir | 10K | выделывать | ✓ | 0✓ | ✓ | ✓ | ✓ | ✓ | ACTIVATION_READY_PREPARED |
| 9328 | inventar | 10K | изобрета́ть | ✓ | 0✓ | ✓ | ✓ | ✓ | ✓ | ACTIVATION_READY_PREPARED |

**Result: 9/9 PASS — GREEN**

## Projected Verb Coverage After Activation

| Metric | Before | After |
|--------|--------|-------|
| Active verbs (all bins) | 176 | 185 |
| Active verbs (10K) | 41 | 50 |

## Apply Script

See `scripts/verb_tranche1_activate_DONOTRUN.sh`.
Default behavior: dry-run only. Pass `--apply` to activate (not done in this task).

