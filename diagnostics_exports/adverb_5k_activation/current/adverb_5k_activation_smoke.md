# Adverb 5K Activation — Stage 4: Smoke Check

**Date:** 2026-04-20

---

## Smoke Checks Run

### 1. vocab_bank QA (`scripts/qa_vocab_bank.sh`)

| Check | Result | Notes |
|-------|--------|-------|
| Total active items | 824 | Expected (was 818 before; +6) |
| Dup lemma in active bank | junto/rosa/rápido | Pre-existing issues, unrelated to this activation |
| 6 activated lemmas: dup count | 1 each | ✓ clean |
| Generic question_text for activated items | "Что значит это слово?" | Pre-existing bank-wide pattern; not introduced here |

### 2. Selector-readiness check (targeted)

| item_id | lemma | is_active | choice_count | correct_count | selector-ready |
|---------|-------|-----------|-------------|---------------|---------------|
| 3958 | frequentemente | 1 | 4 | 1 | ✓ |
| 3960 | geralmente | 1 | 4 | 1 | ✓ |
| 10017 | novamente | 1 | 4 | 1 | ✓ |
| 3963 | principalmente | 1 | 4 | 1 | ✓ |
| 10019 | exatamente | 1 | 4 | 1 | ✓ |
| 3970 | facilmente | 1 | 4 | 1 | ✓ |

### 3. Active adverb distribution by bin (post-activation)

| bin_name | active_count |
|----------|-------------|
| 1K | 25 |
| 2K | 4 |
| 5K | 16 |
| 10K | 1 |

5K adverb pool: 10 → 16 (+6). Consistent with target activation.

### 4. POS drift

| POS | before | after | delta |
|-----|--------|-------|-------|
| adverb | 40 | 46 | +6 ✓ |
| noun | 397 | 397 | 0 ✓ |
| verb | 185 | 185 | 0 ✓ |

### 5. Pre-existing QA issues (not introduced by this activation)

- Dup lemmas (junto/rosa/rápido): existed before; unchanged by this workstream.
- Generic question_text: pre-existing bank-wide convention; unchanged by this workstream.
- No regression in these metrics attributable to adverb 5K activation.

---

## Smoke Verdict

**All activation-specific smoke checks: PASS**
**Pre-existing issues: unchanged, not in scope**
**No runtime regression attributable to this activation.**
