# Verb Tranche1 — Activation Go/No-Go

**Date:** 2026-04-19
**Decision: GO_FOR_VERB_TRANCHE1_ACTIVATION**

---

## Stage Gate Summary

| Stage | Result |
|-------|--------|
| Stage 1 — Target set reconfirmation | CONFIRMED (9/9, all checks green) |
| Stage 2 — Activation pack generation | GREEN (9/9 ACTIVATION_READY_PREPARED, dry-run pass) |
| Stage 3 — Go/No-Go | **GO_FOR_VERB_TRANCHE1_ACTIVATION** |

---

## Decision Basis

- All 9 target items reconfirmed in live staging DB: pos=verb, is_active=0, no dup lemmas
- Rule 1a: PASS on all 9 (post-remediation CAs not in active distractors)
- Rule 1b: PASS on all 9 (post-remediation distractors not in active CAs)
- Choice integrity: 1 correct choice per item, ≥4 total choices per item
- Activation pack artifacts complete: manifest, collision report, activation script, summary
- Dry-run of activation script: all 7 pre-activation checks PASS, no DB changes made
- No activation performed in this task

---

## What Will Change on Activation

| Metric | Before | After |
|--------|--------|-------|
| Active verbs (all bins) | 176 | 185 |
| Active verbs (10K) | 41 | 50 |
| Total active items | 809 | 818 |

---

## Items Ready for Activation

| item_id | lemma | bin | CA |
|---------|-------|-----|----|
| 868 | acelerar | 10K | ускорять |
| 921 | alterar | 10K | изменять |
| 1732 | implementar | 10K | реализовывать |
| 1759 | instalar | 10K | устанавливать |
| 2172 | pintar | 10K | красить |
| 3467 | aproximar | 10K | приближать |
| 3491 | cancelar | 10K | отменять |
| 3509 | curtir | 10K | выделывать |
| 9328 | inventar | 10K | изобрета́ть |

---

## Explicit Scope Boundary

NOT done in this task (deferred to activation workstream):
- `is_active=1` writes — zero performed
- Selector configuration — unchanged
- Runtime logic — unchanged
- Monitoring baseline update — deferred
- noun/10K, adverb tracks — untouched

---

## Operator Summary

Verb tranche1 activation pack is complete and dry-run validated. All 9 items (100% 10K bin) pass all pre-activation checks against the live staging DB. The activation apply script (`scripts/verb_tranche1_activate_DONOTRUN.sh`) requires only `--apply` to execute. Activation will bring verb/10K from 41 → 50 items and total active bank from 809 → 818 items. The system is ready for the activation workstream.

**Next session starter prompt:**
```
Run the next bounded workstream:
VERB TRANCHE1 LIVE ACTIVATION

Context:
- Activation pack is prepared and dry-run validated (commit: see below)
- 9 items: ids 868, 921, 1732, 1759, 2172, 3467, 3491, 3509, 9328
- All 10K bin, all pos=verb, all is_active=0
- Manifest: diagnostics_exports/verb_tranche1/current/verb_tranche1_activation_manifest.json
- Apply script: scripts/verb_tranche1_activate_DONOTRUN.sh
- Current active verbs: 176 (10K: 41)

Mission:
1. Create DB backup
2. Run pre-activation dry-run one final time to confirm clean state
3. Apply activation: bash scripts/verb_tranche1_activate_DONOTRUN.sh --apply data/lingua_staging.db
4. Verify post-activation: all 9 items is_active=1, collision re-check, verb/10K count = 50
5. Run selector smoke test: confirm verb/10K items appear in selector pool
6. Commit result

Constraints:
- staging-only
- no noun/10K changes
- no adverb changes
- no selector/runtime changes beyond what activation requires
- commit only if post-activation validation fully green
```
