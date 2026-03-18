# Community replenishment strategy v1

## Goal

Grow `community_content_items` from clean core to a larger active pool without collapsing into repeated opening patterns.

## Current constraint

Previous generation attempts failed because diversity control happened after generation rather than inside generation.

## New model

`plan -> constrained generation -> light validation`

## Wave contract

- target wave: 12–18 items
- min opener families per wave: 8
- max items per opener family: 2
- contexts per wave: at least 6
- intents per wave: at least 6
- avoid repetitive first-word / first2 / first3 patterns
- keep runtime untouched

## Initial opener families

- Что обычно говорят
- Как обычно называют
- Какая фраза здесь звучит
- Как это лучше спросить
- Что тут чаще имеют в виду
- Как в разговоре говорят
- Какими словами лучше
- Что говорят в такой ситуации
- Как здесь правильно сказать
- Что обычно спрашивают
- Как это обычно формулируют
- Что здесь звучит естественно

## Deliverables of v1

- deterministic offline wave builder
- internal diversity gate
- JSONL + TSV output for review/import
- unit tests for family caps and diversity checks

## Not in scope

- DB import
- runtime changes
- selector changes
- staging restart


## Added in v2

- semantic compatibility layer between context and intent
- generator now rejects structurally diverse but semantically absurd pairs
- full repository suite is currently not a valid gate for this layer because unrelated imports are broken elsewhere


## Added in v3

- authoring now starts from scenario pack rather than loose context+intent composition
- each candidate wave item is grounded in a бытовой scenario with speaker goal and natural wording target
- builder prevents scenario reuse within one wave
- awkward meta stems are explicitly blocked
- wave v2 artifacts are generated as review candidates only, not as auto-import material


## Added in v4

- render cleanup layer removes punctuation artifacts and duplicate tail constructions
- review pack exporter produces TSV/JSON for fast human triage
- generated wave remains review-only until a curated import step is added


## Added in v5

- replenishment wave v3 is generated against the live active bank rather than in isolation
- builder now blocks new items that would worsen live opener concentration
- scenario_pack_v2 is intended to refill a cleaned bank after legacy-prune
- outputs include wave TSV/JSONL, review pack v2, and import preview v2
