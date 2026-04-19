# Adverb Inventory Usability — Stage 2

**DB:** data/lingua_staging.db
**Total inactive adverbs:** 101

## Blocker Summary

| Blocker | Count | Meaning |
|---------|-------|---------|
| `usable_now` | **0** | Passes all current Rule 1 checks |
| `r1b_if_group_activated` | 6 | Safe now; R1b fires if peer group activates first |
| `r1b_fail` | 38 | Distractor(s) are already active correct_answers |
| `r1a_fail` | 4 | Item CA is already an active distractor |
| `dup_lemma_active` | 5 | Lemma already has an active item |
| `zero_choices` | 44 | No vocab_choices rows exist |
| `null_bin` | 4 | bin_name is null |

**Recoverable now:** 0
**Recoverable with distractor rebuild:** 48
**Irrecoverable without structural cleanup:** 53

## By Bin

| bin | usable_now | r1b_if_group | r1b_fail | r1a_fail | dup_lemma | zero_choice | null_bin |
|-----|-----------|--------------|----------|----------|-----------|-------------|----------|
| 10K | 0 | 0 | 5 | 0 | 0 | 0 | 0 |
| 1K | 0 | 0 | 9 | 0 | 4 | 33 | 0 |
| 20K | 0 | 0 | 1 | 0 | 0 | 1 | 0 |
| 2K | 0 | 0 | 2 | 0 | 1 | 0 | 0 |
| 5K | 0 | 6 | 21 | 4 | 0 | 10 | 0 |
| NULL | 0 | 0 | 0 | 0 | 0 | 0 | 4 |

## 10K Bin Detail (target bin for standard tranche pattern)

| item_id | lemma | CA | blocker | detail |
|---------|-------|-----|---------|--------|
| 3973 | seriamente | серьёзно | `r1b_fail` | distractors ['медленно'] are active correct_answers |
| 3974 | simplesmente | просто | `r1b_fail` | distractors ['медленно'] are active correct_answers |
| 3975 | realmente | действительно | `r1b_fail` | distractors ['медленно'] are active correct_answers |
| 3976 | totalmente | полностью | `r1b_fail` | distractors ['медленно'] are active correct_answers |
| 3977 | parcialmente | частично | `r1b_fail` | distractors ['медленно'] are active correct_answers |

## Usable-Now Items

| item_id | bin | lemma | CA | cefr | detail |
|---------|-----|-------|-----|------|--------|

## r1b_if_group_activated Items (need peer ordering / distractor rebuild)

| item_id | bin | lemma | CA | detail |
|---------|-----|-------|-----|--------|
| 3958 | 5K | frequentemente | часто | distractors ['особенно', 'очевидно', 'обычно', 'ясно', 'рано'] are CAs of inacti |
| 3960 | 5K | geralmente | обычно | distractors ['очевидно', 'рано', 'вероятно', 'ясно', 'особенно'] are CAs of inac |
| 10017 | 5K | novamente | снова | distractors ['особенно', 'главным образом', 'рано', 'ясно', 'обычно'] are CAs of |
| 3963 | 5K | principalmente | главным образом | distractors ['обычно', 'очевидно', 'ясно', 'особенно', 'рано'] are CAs of inacti |
| 10019 | 5K | exatamente | точно | distractors ['главным образом', 'ясно', 'особенно', 'очевидно', 'рано'] are CAs  |
| 3970 | 5K | facilmente | легко | distractors ['просто', 'частично', 'серьёзно', 'полностью', 'действительно'] are |
