# ADR-CAT-021 — Real vocab flow branching

## Status
Accepted

## Goal
Patch the real vocab flow layer so it can explicitly branch between legacy and CAT-aware results, instead of only carrying CAT as a sidecar at service level.

## Surface
- `start_flow(...)`
- `answer_flow(...)`

## Canonical rules
- flow reads `cat_route` from service-level result
- flow returns explicit `mode: legacy|cat`
- start-path and answer-path both expose branching
- legacy behavior stays intact when CAT is disabled or absent

## Next
Next layer should patch concrete bot/FSM handlers to consume this flow-level branch and switch the visible user path accordingly.
