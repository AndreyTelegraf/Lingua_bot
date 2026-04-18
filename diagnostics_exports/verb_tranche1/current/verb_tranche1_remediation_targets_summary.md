# Verb Tranche1 Remediation Targets — Stage 1

**Source DB:** data/lingua_staging.db
**Active bank size:** 809 items (808 distinct CAs)

## Target Items

| item_id | lemma | CA | R1a | R1b slots | total dist | slots to fix |
|---------|-------|----|-----|-----------|------------|--------------|
| 868 | acelerar | торопить | YES | 5 | 5 | 5 |
| 921 | alterar | менять | YES | 4 | 5 | 4 |
| 1732 | implementar | выполнять | YES | 4 | 5 | 4 |
| 1759 | instalar | провести | YES | 4 | 5 | 4 |
| 2172 | pintar | писать | YES | 3 | 5 | 3 |
| 3467 | aproximar | оценивать | YES | 4 | 5 | 4 |
| 3491 | cancelar | нарушать | YES | 5 | 5 | 5 |
| 3509 | curtir | дубить | YES | 5 | 5 | 5 |
| 9328 | inventar | изобрета́ть | no | 4 | 5 | 4 |

**Total slots needing replacement: 38**

## acelerar (id=868, bin=10K)

**Correct answer:** `торопить`
**Rule 1a FAIL:** `торопить` is a distractor in active items [2032, 2209, 2645] — the CA itself must change or those active items must drop the word from distractors. *(CA is fixed; active bank distractors cannot be changed here — the CA must be accepted as-is. Rule 1a unblocks itself once the conflicting active distractors are noted as acceptable coexistence OR the inactive item's CA is replaced. See proposal stage.)*

**Distractors:**

- `предпочесть` ← **CONFLICT** (CA of active item 2218)
- `активизировать` ← **CONFLICT** (CA of active item 991)
- `считать` ← **CONFLICT** (CA of active item 1110)
- `прыгать` ← **CONFLICT** (CA of active item 2391)
- `обвинять` ← **CONFLICT** (CA of active item 876)

## alterar (id=921, bin=10K)

**Correct answer:** `менять`
**Rule 1a FAIL:** `менять` is a distractor in active items [1311, 2292] — the CA itself must change or those active items must drop the word from distractors. *(CA is fixed; active bank distractors cannot be changed here — the CA must be accepted as-is. Rule 1a unblocks itself once the conflicting active distractors are noted as acceptable coexistence OR the inactive item's CA is replaced. See proposal stage.)*

**Distractors:**

- `отдыхать` ← **CONFLICT** (CA of active item 2334)
- `принимать` ← **CONFLICT** (CA of active item 884)
- `успеть` ← **CONFLICT** (CA of active item 950)
- `стрелять`
- `переводить` ← **CONFLICT** (CA of active item 2558)

## implementar (id=1732, bin=10K)

**Correct answer:** `выполнять`
**Rule 1a FAIL:** `выполнять` is a distractor in active items [883, 1246, 1324, 2326] — the CA itself must change or those active items must drop the word from distractors. *(CA is fixed; active bank distractors cannot be changed here — the CA must be accepted as-is. Rule 1a unblocks itself once the conflicting active distractors are noted as acceptable coexistence OR the inactive item's CA is replaced. See proposal stage.)*

**Distractors:**

- `обвинить` ← **CONFLICT** (CA of active item 1321)
- `болеть` ← **CONFLICT** (CA of active item 1414)
- `катиться`
- `прекращать` ← **CONFLICT** (CA of active item 1181)
- `давить` ← **CONFLICT** (CA of active item 2227)

## instalar (id=1759, bin=10K)

**Correct answer:** `провести`
**Rule 1a FAIL:** `провести` is a distractor in active items [884, 950, 2334] — the CA itself must change or those active items must drop the word from distractors. *(CA is fixed; active bank distractors cannot be changed here — the CA must be accepted as-is. Rule 1a unblocks itself once the conflicting active distractors are noted as acceptable coexistence OR the inactive item's CA is replaced. See proposal stage.)*

**Distractors:**

- `предложить` ← **CONFLICT** (CA of active item 2482)
- `обожать` ← **CONFLICT** (CA of active item 883)
- `нравиться`
- `приспособить` ← **CONFLICT** (CA of active item 878)
- `охотиться` ← **CONFLICT** (CA of active item 1167)

## pintar (id=2172, bin=10K)

**Correct answer:** `писать`
**Rule 1a FAIL:** `писать` is a distractor in active items [499, 522, 636, 1408, 1953, 2222, 2455] — the CA itself must change or those active items must drop the word from distractors. *(CA is fixed; active bank distractors cannot be changed here — the CA must be accepted as-is. Rule 1a unblocks itself once the conflicting active distractors are noted as acceptable coexistence OR the inactive item's CA is replaced. See proposal stage.)*

**Distractors:**

- `расширить` ← **CONFLICT** (CA of active item 1532)
- `стрелять`
- `будить` ← **CONFLICT** (CA of active item 1378)
- `провести`
- `исчезать` ← **CONFLICT** (CA of active item 1369)

## aproximar (id=3467, bin=10K)

**Correct answer:** `оценивать`
**Rule 1a FAIL:** `оценивать` is a distractor in active items [1301, 2072, 2430, 2659] — the CA itself must change or those active items must drop the word from distractors. *(CA is fixed; active bank distractors cannot be changed here — the CA must be accepted as-is. Rule 1a unblocks itself once the conflicting active distractors are noted as acceptable coexistence OR the inactive item's CA is replaced. See proposal stage.)*

**Distractors:**

- `мечтать` ← **CONFLICT** (CA of active item 2470)
- `менять` ← **CONFLICT** (CA of active item 10002)
- `дубить`
- `целовать` ← **CONFLICT** (CA of active item 1047)
- `отбиваться` ← **CONFLICT** (CA of active item 3615)

## cancelar (id=3491, bin=10K)

**Correct answer:** `нарушать`
**Rule 1a FAIL:** `нарушать` is a distractor in active items [1301, 2072, 2430, 2659] — the CA itself must change or those active items must drop the word from distractors. *(CA is fixed; active bank distractors cannot be changed here — the CA must be accepted as-is. Rule 1a unblocks itself once the conflicting active distractors are noted as acceptable coexistence OR the inactive item's CA is replaced. See proposal stage.)*

**Distractors:**

- `отбиваться` ← **CONFLICT** (CA of active item 3615)
- `целовать` ← **CONFLICT** (CA of active item 1047)
- `менять` ← **CONFLICT** (CA of active item 10002)
- `мечтать` ← **CONFLICT** (CA of active item 2470)
- `переводить` ← **CONFLICT** (CA of active item 2558)

## curtir (id=3509, bin=10K)

**Correct answer:** `дубить`
**Rule 1a FAIL:** `дубить` is a distractor in active items [1301, 1401, 2075, 2292, 2401, 2430, 9999] — the CA itself must change or those active items must drop the word from distractors. *(CA is fixed; active bank distractors cannot be changed here — the CA must be accepted as-is. Rule 1a unblocks itself once the conflicting active distractors are noted as acceptable coexistence OR the inactive item's CA is replaced. See proposal stage.)*

**Distractors:**

- `нанимать` ← **CONFLICT** (CA of active item 1251)
- `предать` ← **CONFLICT** (CA of active item 2560)
- `болеть` ← **CONFLICT** (CA of active item 1414)
- `переводить` ← **CONFLICT** (CA of active item 2558)
- `охотиться` ← **CONFLICT** (CA of active item 1167)

## inventar (id=9328, bin=10K)

**Correct answer:** `изобрета́ть`

**Distractors:**

- `активизировать` ← **CONFLICT** (CA of active item 991)
- `бегать` ← **CONFLICT** (CA of active item 431)
- `болеть` ← **CONFLICT** (CA of active item 1414)
- `бросить`
- `будить` ← **CONFLICT** (CA of active item 1378)

