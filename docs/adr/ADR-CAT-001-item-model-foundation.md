# ADR-CAT-001 — CAT item model foundation

## Status
Accepted

## Context
We need a canonical CAT item contract before implementing:
- estimator (theta / SE),
- information-based selection,
- stopping rules,
- calibration.

Without a strict item model, CAT runtime becomes heuristic and non-auditable.

## Decision
Introduce a minimal canonical CAT item model with:
- psychometric params: a / b / c / d
- pedagogical tags: CEFR / skill / content
- product flags: modality / active / exposure cap

## Consequences
This layer does not change runtime behavior yet.
It only defines:
- stable contract,
- validation rules,
- testable foundation for next CAT layers.

## Next
1. estimator contract
2. selector contract
3. stopping rules contract
