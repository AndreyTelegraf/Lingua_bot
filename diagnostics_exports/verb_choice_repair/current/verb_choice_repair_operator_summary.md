# Verb Choice Repair — Operator Summary

**Workstream:** PREPARE-ONLY REPAIR OF INACTIVE VERB ITEMS WITH MISSING VOCAB_CHOICES
**Mode:** prepare-only — no DB writes have been made

---

## Stage Gate Summary

| Stage | Result |
|-------|--------|
| Stage 1 — Target pool reconfirmation | PASS |
| Stage 2 — Choice reconstruction proposals | PASS |
| Stage 3 — Validation of proposed repairs | PASS |
| Stage 4 — Prepare-only apply pack | PASS |

---

## Counts

| Metric | Count |
|--------|-------|
| Total target pool | 70 |
| READY (proposals pass all checks) | **2** |
| REVIEW (blocked by active bank conflicts) | 2 |
| REJECT (irrecoverable in this workstream) | 66 |
| **Recoverable now (apply scope)** | **2** |
| Recoverable with bank surgery (REVIEW) | 2 |

---

## READY Items (apply scope)

| item_id | lemma | bin | CA | Distractors |
|---------|-------|-----|----|-------------|
| 10628 | reconhecer | NULL | узнавать | признавать/наблюдать/запоминать |
| 10647 | ferir | NULL | ранить | бить/избивать/повреждать |

---

## REVIEW Items (require active bank distractor rebuild before activation)

| item_id | lemma | CA | Blocker |
|---------|-------|-----|---------|
| 8742 | admirar | — | r1a_clash: CA 'восхищаться' appears as distractor in active items; Rule 1a would |
| 9692 | regular | — | r1a_clash: CA 'регулировать' appears as distractor in active items; Rule 1a woul |

---

## Why 66 Items Are REJECT

- **60 items**: lemma already present in the active verb bank (true duplicates). Adding choices would create irreconcilable dup-lemma conflicts if ever activated. Root cause: broken imports created multiple rows per lemma.
- **3 items** (9322, 9324, 9689): correct_answer already used as an active correct_answer (dup CA; also cognate transparency risk on 9324).
- **2 items** (1273, 2718): wrong gloss — `contar` does not mean `читать`; also dup CA + Rule 1a violations.
- **1 item** (9195): vulgar/obscene CA (`ети`) — not suitable for vocab bank.
- **1 item** (2699): falar/сказать — CA is both an active CA and an active distractor.
- **2 items** (1265, 2716): conhecer/знать — same as falar plus are pool duplicates.

---

## Apply Pack

Apply script: `scripts/verb_choice_repair_apply_DONOTRUN.sh`
Apply manifest: `diagnostics_exports/verb_choice_repair/current/verb_choice_repair_apply_manifest.json`

To execute (when authorized in a future workstream):
```
bash scripts/verb_choice_repair_apply_DONOTRUN.sh data/lingua_staging.db --apply
```

**Default is dry-run. The `--apply` flag was NOT used in this workstream.**

---

## Recommendation

**A future apply workstream IS JUSTIFIED for the 2 READY item(s).**

These items have structurally valid 4-choice sets, pass Rule 1a and Rule 1b, and their lemmas are not in the active bank. They are currently inactive and will remain so after the choice repair — activation requires a separate activation workstream with full stage gates.

The {len(review_items)} REVIEW items require the active bank's distractor sets to be rebuilt (removing the conflicting CA from those distractors) before they can be safely activated. This is a separate, bounded workstream.

The 60 dup-lemma REJECT items are not recoverable without a deduplication cleanup of the raw item table, which is out of scope for this workstream.
