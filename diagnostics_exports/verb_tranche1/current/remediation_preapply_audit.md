# Verb Tranche1 Remediation — Pre-Apply Safety Audit

**DB:** data/lingua_staging.db
**Apply script:** scripts/verb_tranche1_remediation_apply_DONOTRUN.sh
**Commit anchor:** 8996afe

## Check Results

| Check | Result |
|-------|--------|
| Target IDs match manifest | PASS |
| No is_active in apply script | PASS |
| Only vocab_items/vocab_choices touched | PASS |
| Pre-apply CA state consistent | PASS |
| Choice_id ownership correct | PASS |

## Scope Summary

- **Tables touched:** `vocab_items` (correct_answer), `vocab_choices` (choice_text)
- **Target items:** [868, 921, 1732, 1759, 2172, 3467, 3491, 3509, 9328]
- **vocab_items CA updates:** 8 rows
- **vocab_choices correct-row updates:** 8 rows
- **vocab_choices distractor updates:** 38 rows
- **is_active changes:** NONE
- **Activation logic present:** NO

## Pre-Apply CA State

| item_id | current CA | expected old | expected new | state |
|---------|-----------|--------------|--------------|-------|
| 868 | торопить | торопить | ускорять | READY |
| 921 | менять | менять | изменять | READY |
| 1732 | выполнять | выполнять | реализовывать | READY |
| 1759 | провести | провести | устанавливать | READY |
| 2172 | писать | писать | красить | READY |
| 3467 | оценивать | оценивать | приближать | READY |
| 3491 | нарушать | нарушать | отменять | READY |
| 3509 | дубить | дубить | выделывать | READY |

## Choice Ownership Check

| choice_id | current text | item_id | state |
|-----------|-------------|---------|-------|
| 403627 | предпочесть | 868 | READY |
| 403628 | активизировать | 868 | READY |
| 403630 | считать | 868 | READY |
| 403631 | прыгать | 868 | READY |
| 403632 | обвинять | 868 | READY |
| 403124 | отдыхать | 921 | READY |
| 403125 | принимать | 921 | READY |
| 403126 | успеть | 921 | READY |
| 403128 | переводить | 921 | READY |
| 403382 | обвинить | 1732 | READY |
| 403383 | болеть | 1732 | READY |
| 403385 | прекращать | 1732 | READY |
| 403386 | давить | 1732 | READY |
| 403261 | предложить | 1759 | READY |
| 403263 | обожать | 1759 | READY |
| 403265 | приспособить | 1759 | READY |
| 403266 | охотиться | 1759 | READY |
| 403171 | расширить | 2172 | READY |
| 403173 | будить | 2172 | READY |
| 403175 | исчезать | 2172 | READY |
| 403081 | мечтать | 3467 | READY |
| 403082 | менять | 3467 | READY |
| 403084 | целовать | 3467 | READY |
| 403085 | отбиваться | 3467 | READY |
| 403087 | отбиваться | 3491 | READY |
| 403088 | целовать | 3491 | READY |
| 403089 | менять | 3491 | READY |
| 403091 | мечтать | 3491 | READY |
| 403092 | переводить | 3491 | READY |
| 433777 | нанимать | 3509 | READY |
| 433778 | предать | 3509 | READY |
| 433779 | болеть | 3509 | READY |
| 433780 | переводить | 3509 | READY |
| 433781 | охотиться | 3509 | READY |
| 404780 | активизировать | 9328 | READY |
| 404781 | бегать | 9328 | READY |
| 404782 | болеть | 9328 | READY |
| 404784 | будить | 9328 | READY |

## Overall: **SAFE_TO_PROCEED**

