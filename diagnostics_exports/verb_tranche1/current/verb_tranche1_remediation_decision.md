# Verb Tranche1 Distractor Remediation — Stage 4 Final Decision

**Date:** 2026-04-18
**Status:** REMEDIATION_SUCCEEDED

---

## Verdict

**REMEDIATION_SUCCEEDED.** All 9 target items pass Rule 1a, Rule 1b, and intra-tranche conflict checks with proposed changes applied. The tranche is ready to apply once the apply script receives human sign-off.

---

## Summary

| Stage | Result |
|-------|--------|
| Stage 1 — Collision extraction | 9 items, 38 conflict slots identified |
| Stage 2 — Replacement proposals | 38/38 slots filled, 9/9 items fully remediated |
| Stage 3 — Post-remediation check | 9/9 PASS (R1a, R1b, intra-tranche) |
| Stage 4 — Decision | **REMEDIATION_SUCCEEDED** |

---

## Tranche Composition

- **Items selected:** 9
- **Bin:** 10K × 9
- **Items excluded from tranche:** 24 non-10K READY items (20K/5K/2K/1K bins) — deferred, not remediated in this pass

---

## Changes Required Per Item

| item_id | lemma | CA change | Distractors replaced |
|---------|-------|-----------|---------------------|
| 868 | acelerar | торопить → ускорять | 5/5 |
| 921 | alterar | менять → изменять | 4/5 |
| 1732 | implementar | выполнять → реализовывать | 4/5 |
| 1759 | instalar | провести → устанавливать | 4/5 |
| 2172 | pintar | писать → красить | 3/5 |
| 3467 | aproximar | оценивать → приближать | 4/5 |
| 3491 | cancelar | нарушать → отменять | 5/5 |
| 3509 | curtir | дубить → выделывать | 5/5 |
| 9328 | inventar | (kept: изобрета́ть) | 4/5 |

**Total:** 8 CA changes, 38 distractor replacements.

---

## Apply Instructions

1. Human review: `scripts/verb_tranche1_remediation_apply_DONOTRUN.sh`
   - Verify each SQL UPDATE references the correct `choice_id` and `item_id`
   - Spot-check CA translations for semantic accuracy (see notes below)
2. Run against staging only:
   ```
   bash scripts/verb_tranche1_remediation_apply_DONOTRUN.sh data/lingua_staging.db
   ```
3. Re-run validator to confirm live DB state:
   ```
   python3 scripts/verb_tranche1_remediation_validate.py --db data/lingua_staging.db
   ```
4. If validator returns 9/9 PASS: proceed to Stage B activation prep.

---

## Semantic Notes for Human Review

- **acelerar → ускорять**: correct primary gloss (to accelerate/speed up). "разгонять" (distractor) is semantically adjacent — acceptable, not ambiguous.
- **alterar → изменять**: both mean "to change/alter". изменять is the stronger/more precise Russian gloss.
- **implementar → реализовывать**: standard technical gloss; воплощать would also be valid but реализовывать is closer for technical contexts.
- **instalar → устанавливать**: direct 1-to-1 technical gloss match.
- **pintar → красить**: covers "to paint (with paint)." Note: рисовать (to draw/paint artistically) was the original CA — красить is the more precise gloss for paint application. Acceptable.
- **aproximar → приближать**: "to approach/bring near" — correct.
- **cancelar → отменять**: "to cancel" — correct.
- **curtir (leather) → выделывать**: "to tan/dress leather" — нишевое, but correct for the тanning domain. Distractor set (замачивать, очищать, смягчать, пропитывать, отмачивать) is semantically coherent within leather-working domain — no cognate transparency issue.
- **inventar → изобрета́ть**: CA kept; accent mark present — verify DB stores it correctly.

---

## 10K Tranche Target

The original execution plan targeted the 10K bin for verb tranche1. All 9 selected items are 10K. The active bank currently has 30 verb items (all bins) active. Adding 9 × 10K verbs expands verb 10K coverage meaningfully.

The 24 non-10K READY items (bins: 20K, 5K, 2K, 1K) were not remediated in this pass. They can be addressed in a future tranche with the same remediation pattern.

---

## Next Session Starter

```
Verb tranche1 distractor remediation is COMPLETE (9/9 PASS).
Apply script: scripts/verb_tranche1_remediation_apply_DONOTRUN.sh
Manifest: diagnostics_exports/verb_tranche1/current/verb_tranche1_post_remediation_manifest.json
Validator: scripts/verb_tranche1_remediation_validate.py

Next step: human review of apply script → run against staging → re-validate → Stage B activation prep
(Stage B: build activation import artifact from manifest, set is_active=1 for 9 items)
```
