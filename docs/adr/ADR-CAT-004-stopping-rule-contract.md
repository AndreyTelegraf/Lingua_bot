# ADR-CAT-004 — CAT stopping rule contract

## Status
Accepted

## Context
After item model, estimator, and selector, CAT needs a canonical stopping rule.
The engine must know when to stop adaptively and return a stable estimate.

## Decision
Introduce:
- CATStoppingDecision
- should_stop_cat(...)

Stopping policy:
1. hard stop when questions_answered >= max_questions
2. no adaptive stop before min_questions
3. after min_questions, stop when current_se <= target_se
4. otherwise continue

Default contract:
- min_questions = 8
- max_questions = 24
- target_se = 0.35

## Consequences
This creates a deterministic and testable stop layer.
It is sufficient for first CAT session orchestration.

## Next
1. CAT session state contract
2. CAT loop orchestration contract
3. integration into Level/CIPLE runtime
