# Verb Tranche1 Remediation — Final Go/No-Go

**Date:** 2026-04-19
**Decision: GO_FOR_VERB_TRANCHE1_ACTIVATION_PREP**

---

## Stage Gate Summary

| Stage | Result |
|-------|--------|
| Stage 1 — Pre-apply safety audit | PASS (all 5 checks green) |
| Stage 2 — Apply remediation to staging | PASS (38 rows updated, active count unchanged) |
| Stage 3 — Live validation | PASS (9/9 items, all checks green) |
| Stage 4 — Go/No-Go | **GO_FOR_VERB_TRANCHE1_ACTIVATION_PREP** |

---

## Decision Basis

- Remediation fully applied to `data/lingua_staging.db`
- Live validation confirms: all 9 target items are `is_active=0`, all CAs and distractors match the approved manifest
- Rule 1a: PASS on all 9 items
- Rule 1b: PASS on all 9 items
- Choice integrity: 1 correct choice per item, 5 distractors per item
- Active bank unchanged: 809 items, no activation occurred
- No unintended tables or columns touched

---

## Items Ready for Activation Prep

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

## What Has NOT Been Done (Explicit Scope Boundary)

- Items are **not activated** (`is_active` remains 0)
- No activation pack (import artifact) has been built
- No selector configuration has been changed
- No runtime logic has been touched
- noun/10K and adverb tracks unchanged

---

## Operator Summary

Verb tranche1 distractor remediation is now fully applied and validated on staging. All 9 non-duplicate 10K READY verb items (acelerar, alterar, implementar, instalar, pintar, aproximar, cancelar, curtir, inventar) pass Rule 1a, Rule 1b, and intra-tranche conflict checks in the live DB. The active bank remains at 809 items — no activation has occurred. The system is ready for the next bounded workstream: build the verb tranche1 activation pack (set `is_active=1` for these 9 items, verify selector coverage, run contract smoke tests).

**Next session starter prompt:**
```
Run the next bounded workstream:
VERB TRANCHE1 ACTIVATION PACK

Context:
- Verb tranche1 remediation is fully applied and validated on staging (commit: see below)
- 9 items are collision-clean, is_active=0, all in 10K bin
- Manifest: diagnostics_exports/verb_tranche1/current/verb_tranche1_post_remediation_manifest.json
- Live validation: diagnostics_exports/verb_tranche1/current/remediation_live_validation.json
- Active bank: 809 items

Mission:
Build and apply the verb tranche1 activation pack:
1. Prepare activation import artifact (item IDs + is_active=1 patch script)
2. Apply is_active=1 to all 9 manifest items on staging
3. Verify post-activation selector coverage for verb/10K bin
4. Run contract smoke test (collision re-check with active bank now including new items)
5. Confirm monitoring baseline: verb/10K item count, selector exposure cap

Constraints:
- staging-only
- no noun/10K changes
- no adverb changes
- no selector/runtime changes beyond what activation requires
- commit only if all acceptance checks green
```
