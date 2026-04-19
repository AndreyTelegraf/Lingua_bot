# Verb Choice Repair — Stage 3: Validation

**DB:** data/lingua_staging.db

## Summary

| Category | Count |
|----------|-------|
| Total proposals | 70 |
| READY proposals | 2 |
| REVIEW proposals | 2 |
| REJECT proposals | 66 |
| Validated READY (pass all checks) | **2** |
| Validation failed | 0 |

## Validation Results (READY items only)

| item_id | lemma | CA | Distractors | PASS |
|---------|-------|-----|-------------|------|
| 10628 | reconhecer | узнавать | признавать/наблюдать/запоминать | **PASS** |
| 10647 | ferir | ранить | бить/избивать/повреждать | **PASS** |

## REVIEW Items (require bank surgery before activation)

| item_id | lemma | CA | Blocker |
|---------|-------|-----|---------|
| 8742 | admirar | восхищаться | r1a_clash: CA 'восхищаться' appears as distractor in active items; Rule 1a would |
| 9692 | regular | регулировать | r1a_clash: CA 'регулировать' appears as distractor in active items; Rule 1a woul |

**Recoverable now (READY + pass all checks): 2**
**Recoverable with bank fix (REVIEW): 2**
**Irrecoverable in this workstream (REJECT): 66**
