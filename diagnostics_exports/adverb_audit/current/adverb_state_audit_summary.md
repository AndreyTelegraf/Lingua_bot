# Adverb State Audit — Stage 1

**DB:** data/lingua_staging.db

## Active Adverbs

| Metric | Value |
|--------|-------|
| Total active | 40 |
| Zero-choice | 0 |
| Null bin | 0 |
| Dup lemmas (count) | 0 |

**Active by bin:**

| bin | count |
|-----|-------|
| 10K | 1 |
| 1K | 25 |
| 2K | 4 |
| 5K | 10 |

## Inactive Adverbs

| Metric | Value |
|--------|-------|
| Total inactive | 101 |
| With 6 choices | 57 |
| Zero-choice | 44 |
| Other choice count | 0 |
| Null bin | 4 |
| Dup lemma lemmas | 24 |
| Dup excess rows | 28 |

**Inactive by bin:**

| bin | count |
|-----|-------|
| 10K | 5 |
| 1K | 46 |
| 20K | 2 |
| 2K | 3 |
| 5K | 41 |
| NULL | 4 |

**Inactive dup lemmas:** abaixo(×2), acima(×2), ali(×2), antes(×2), aqui(×2), assim(×2), claramente(×2), depois(×2), especialmente(×2), facilmente(×2), junto(×2), lentamente(×2), mal(×5), mesmo(×2), nunca(×2), obviamente(×2), ontem(×2), outrora(×2), perto(×2), pior(×3), possivelmente(×2), principalmente(×2), provavelmente(×2), rapidamente(×2)

## Key Structural Observations

- Active bank: 40 adverbs, no zero-choice items, no dup lemmas, no null bins.
- Inactive pool: 101 items, 44 have zero choices (mostly dup-lemma duplicates).
- Inactive pool has 28 excess rows from dup-lemma inflation (73 unique lemmas, 101 rows).
- 10K inactive bin: 5 items, all have 6 choices.
- 5K inactive bin: 41 items; 57 six-choice inactive items total across all bins.
- 20K inactive bin: 2 items (outrora×2: one with 6 choices, one zero-choice).
