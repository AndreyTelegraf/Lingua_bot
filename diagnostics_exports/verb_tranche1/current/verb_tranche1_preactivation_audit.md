# Verb Tranche1 — Pre-Activation Safety Audit

**DB:** data/lingua_staging.db
**Date:** 2026-04-19
**Anchor commit:** cb19545

## Check Results

| Check | Result |
|-------|--------|
| Target IDs match manifest | PASS |
| All 9 items still is_active=0 | PASS |
| All items pass R1a/R1b/dup/integrity | PASS |
| No forbidden tables in script | PASS |
| Script only modifies is_active | PASS |
| Script UPDATE targets exactly match manifest IDs | PASS |

## Target Items

| item_id | lemma | pos | CA | R1a | R1b | no_dup | integrity | PASS |
|---------|-------|-----|-----|-----|-----|--------|-----------|------|
| 868 | acelerar | verb | ускорять | ✓ | ✓ | ✓ | ✓ | **PASS** |
| 921 | alterar | verb | изменять | ✓ | ✓ | ✓ | ✓ | **PASS** |
| 1732 | implementar | verb | реализовывать | ✓ | ✓ | ✓ | ✓ | **PASS** |
| 1759 | instalar | verb | устанавливать | ✓ | ✓ | ✓ | ✓ | **PASS** |
| 2172 | pintar | verb | красить | ✓ | ✓ | ✓ | ✓ | **PASS** |
| 3467 | aproximar | verb | приближать | ✓ | ✓ | ✓ | ✓ | **PASS** |
| 3491 | cancelar | verb | отменять | ✓ | ✓ | ✓ | ✓ | **PASS** |
| 3509 | curtir | verb | выделывать | ✓ | ✓ | ✓ | ✓ | **PASS** |
| 9328 | inventar | verb | изобрета́ть | ✓ | ✓ | ✓ | ✓ | **PASS** |

## Current Bank State

- Active verbs (all bins): 176
- Active verbs (10K): 41
- Active noun/10K: 13
- Active adverbs: 40

## Overall: **SAFE_TO_PROCEED**

