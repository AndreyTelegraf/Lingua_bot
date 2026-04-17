# Vocab Diagnostic Contract

## Goal
Each item must measure lexical knowledge, not pattern recognition, cognate guessing, morphology guessing, or distractor elimination tricks.

## A valid diagnostic item must satisfy all
1. The correct answer is not transparent to a strong RU/EN speaker without knowing the Portuguese word.
2. Distractors are plausible and in-range.
3. Distractors do not contain obvious “junk” options.
4. The item difficulty matches the claimed band.
5. The Russian gloss is natural and not broader/narrower than the target sense.
6. The item is not a near-duplicate of an existing lemma/concept/test function.
7. The item discriminates between adjacent skill levels.
8. The item is robust under manual smoke.

## Immediate reject conditions
- transparent_cognate
- internationalism
- obvious_suffix_pattern
- morphology_giveaway
- broken_distractor
- duplicate_lemma
- duplicate_concept
- duplicate_test_function
- too_easy_for_band
- weird_or_unusable_register
- ambiguous_gloss
- ambiguous_prompt
- distractor_register_mismatch

## Hold conditions
- borderline transparency
- plausible but weak distractor set
- sense calibration uncertainty
- band uncertainty
- unclear duplicate risk

## Approval bar
Approve only if the item would survive adversarial review by a skeptical human reviewer.
