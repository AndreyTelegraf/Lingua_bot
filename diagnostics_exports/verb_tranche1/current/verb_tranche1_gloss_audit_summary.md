# Verb Tranche1 Gloss Audit — Stage A Summary

**Audit date:** 2026-04-18T13:50:59Z
**DB:** data/lingua_staging.db
**Scope:** inactive verbs (`is_active=0`, `pos='verb'`)

## Candidate Counts

| Class  | Count |
|--------|-------|
| READY   | 33 |
| REVIEW   | 30 |
| REJECT   | 70 |
| **TOTAL** | **133** |

## By Bin

| Bin  | READY | REVIEW | REJECT | Total |
|------|-------|--------|--------|-------|
| 1K   | 7 | 0 | 53 | 60 |
| 2K   | 8 | 0 | 0 | 8 |
| 5K   | 7 | 4 | 4 | 15 |
| 10K   | 10 | 4 | 3 | 17 |
| 20K   | 1 | 1 | 8 | 10 |
| NULL   | 0 | 21 | 2 | 23 |

## Top Rule Flags

- `not_infinitive_like`: 72 items
- `latin_chars_in_ru_gloss`: 70 items
- `lemma_phonetic_copy`: 70 items
- `english_leakage`: 68 items
- `reflexive_infinitive`: 6 items
- `phrase_like_gloss`: 6 items
- `generic_ai_gloss`: 2 items
- `pt_suffix:izar`: 2 items
- `ru_internationalism`: 1 items
- `non_verb_gloss_candidate`: 1 items

## Stage B Recommendation

**Justified:** YES

Stage B is justified: sufficient READY/REVIEW items in 10K+20K to assemble a candidate pool.

- READY in 10K: 10
- READY in 20K: 1
- REVIEW in 10K (may pass human check): 4
- REVIEW in 20K (may pass human check): 1

## REJECT Detail

Items in REJECT with their primary rejection reason:

- `interessar` (id=9322, bin=10K): no_correct_answer_in_vocab_choices
- `interpretar` (id=9324, bin=10K): no_correct_answer_in_vocab_choices
- `registrar` (id=9689, bin=10K): no_correct_answer_in_vocab_choices
- `comer` (id=23, bin=1K): no_correct_answer_in_vocab_choices
- `trabalhar` (id=27, bin=1K): no_correct_answer_in_vocab_choices
- `trabalhar` (id=50, bin=1K): no_correct_answer_in_vocab_choices
- `trabalhar` (id=148, bin=1K): no_correct_answer_in_vocab_choices
- `ajudar` (id=898, bin=1K): no_correct_answer_in_vocab_choices
- `comer` (id=1240, bin=1K): no_correct_answer_in_vocab_choices
- `começar` (id=1242, bin=1K): no_correct_answer_in_vocab_choices
- `comprar` (id=1249, bin=1K): no_correct_answer_in_vocab_choices
- `conhecer` (id=1265, bin=1K): no_correct_answer_in_vocab_choices
- `contar` (id=1273, bin=1K): no_correct_answer_in_vocab_choices
- `dormir` (id=1418, bin=1K): no_correct_answer_in_vocab_choices
- `encontrar` (id=1455, bin=1K): no_correct_answer_in_vocab_choices
- `entender` (id=1462, bin=1K): no_correct_answer_in_vocab_choices
- `esperar` (id=1501, bin=1K): no_correct_answer_in_vocab_choices
- `ficar` (id=1572, bin=1K): no_correct_answer_in_vocab_choices
- `ler` (id=1848, bin=1K): no_correct_answer_in_vocab_choices
- `mostrar` (id=2006, bin=1K): no_correct_answer_in_vocab_choices
- `ouvir` (id=2095, bin=1K): no_correct_answer_in_vocab_choices
- `pagar` (id=2100, bin=1K): no_correct_answer_in_vocab_choices
- `parar` (id=2120, bin=1K): no_correct_answer_in_vocab_choices
- `seguir` (id=2408, bin=1K): no_correct_answer_in_vocab_choices
- `sentir` (id=2429, bin=1K): no_correct_answer_in_vocab_choices
- `tentar` (id=2521, bin=1K): no_correct_answer_in_vocab_choices
- `tomar` (id=2548, bin=1K): no_correct_answer_in_vocab_choices
- `trabalhar` (id=2554, bin=1K): no_correct_answer_in_vocab_choices
- `usar` (id=2603, bin=1K): no_correct_answer_in_vocab_choices
- `ver` (id=2627, bin=1K): no_correct_answer_in_vocab_choices
- `viver` (id=2656, bin=1K): no_correct_answer_in_vocab_choices
- `ver` (id=2698, bin=1K): no_correct_answer_in_vocab_choices
- `falar` (id=2699, bin=1K): no_correct_answer_in_vocab_choices
- `ficar` (id=2700, bin=1K): no_correct_answer_in_vocab_choices
- `usar` (id=2701, bin=1K): no_correct_answer_in_vocab_choices
- `ajudar` (id=2702, bin=1K): no_correct_answer_in_vocab_choices
- `encontrar` (id=2704, bin=1K): no_correct_answer_in_vocab_choices
- `começar` (id=2705, bin=1K): no_correct_answer_in_vocab_choices
- `ouvir` (id=2706, bin=1K): no_correct_answer_in_vocab_choices
- `trabalhar` (id=2707, bin=1K): no_correct_answer_in_vocab_choices
- `viver` (id=2708, bin=1K): no_correct_answer_in_vocab_choices
- `seguir` (id=2709, bin=1K): no_correct_answer_in_vocab_choices
- `tomar` (id=2710, bin=1K): no_correct_answer_in_vocab_choices
- `comprar` (id=2711, bin=1K): no_correct_answer_in_vocab_choices
- `ler` (id=2712, bin=1K): no_correct_answer_in_vocab_choices
- `parar` (id=2713, bin=1K): no_correct_answer_in_vocab_choices
- `tentar` (id=2714, bin=1K): no_correct_answer_in_vocab_choices
- `sentir` (id=2715, bin=1K): no_correct_answer_in_vocab_choices
- `conhecer` (id=2716, bin=1K): no_correct_answer_in_vocab_choices
- `mostrar` (id=2717, bin=1K): no_correct_answer_in_vocab_choices
- `contar` (id=2718, bin=1K): no_correct_answer_in_vocab_choices
- `comer` (id=2719, bin=1K): no_correct_answer_in_vocab_choices
- `entender` (id=2720, bin=1K): no_correct_answer_in_vocab_choices
- `pagar` (id=2721, bin=1K): no_correct_answer_in_vocab_choices
- `esperar` (id=2722, bin=1K): no_correct_answer_in_vocab_choices
- `dormir` (id=2723, bin=1K): no_correct_answer_in_vocab_choices
- `acomodar` (id=8736, bin=20K): no_correct_answer_in_vocab_choices
- `admirar` (id=8742, bin=20K): no_correct_answer_in_vocab_choices
- `ativar` (id=8804, bin=20K): no_correct_answer_in_vocab_choices
- `calcular` (id=8881, bin=20K): no_correct_answer_in_vocab_choices
- `diferenciar` (id=9063, bin=20K): no_correct_answer_in_vocab_choices
- `fomentar` (id=9197, bin=20K): no_correct_answer_in_vocab_choices
- `preferir` (id=9620, bin=20K): no_correct_answer_in_vocab_choices
- `vomitar` (id=9908, bin=20K): no_correct_answer_in_vocab_choices
- `analisar` (id=8769, bin=5K): no_correct_answer_in_vocab_choices
- `aproveitar` (id=8784, bin=5K): no_correct_answer_in_vocab_choices
- `foder` (id=9195, bin=5K): no_correct_answer_in_vocab_choices
- `regular` (id=9692, bin=5K): no_correct_answer_in_vocab_choices
- `reconhecer` (id=10628, bin=None): no_correct_answer_in_vocab_choices
- `ferir` (id=10647, bin=None): no_correct_answer_in_vocab_choices

## REVIEW Items in Priority Bins (10K + 20K)

These require human gloss check before Stage B inclusion:

- `agradar` (id=895, bin=10K, gloss=`нравиться`): reflexive_infinitive:acceptable_but_flag_for_review
- `executar` (id=1529, bin=10K, gloss=`делать`): gloss_rule:generic_ai_gloss
- `rezar` (id=2362, bin=10K, gloss=`молиться`): reflexive_infinitive:acceptable_but_flag_for_review
- `rolar` (id=2371, bin=10K, gloss=`катиться`): reflexive_infinitive:acceptable_but_flag_for_review
- `admirar` (id=881, bin=20K, gloss=`восхищаться`): reflexive_infinitive:acceptable_but_flag_for_review
