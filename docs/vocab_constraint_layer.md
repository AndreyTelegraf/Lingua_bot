# Vocab Constraint Layer

## Purpose
This layer exists to prevent structural bank corruption before any candidate reaches staging.

## Rule 1 — Anti-collision
A correct_answer must not appear as a distractor in any other active vocab item.
Preferred policy: global ban across the active vocab bank.
Minimum policy: forbid within the same band and adjacent bands.

## Rule 2 — Anti-transparency
Reject or hold candidates that are guessable through:
- international roots
- obvious cognates
- transparent suffix patterns
- morphology giveaways
- weak distractor elimination

## Rule 3 — Controlled growth
One growth wave may target exactly one segment only:
- one pos
- one bin_name

## Mandatory checks before staging
Every approved candidate set must be checked for:
- distractor collisions against all active correct answers
- duplicate lemma
- duplicate concept_group if available
- missing fields
- malformed distractor sets
- transparency / cognate risk

## Decision rule
If in doubt:
- hold
- or reject

False positives are worse than false negatives.
