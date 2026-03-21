# ADR-CAT-002 — CAT estimator contract

## Status
Accepted

## Context
After defining the CAT item model, we need a canonical estimator contract:
- theta
- standard error
- information
- convergence flag

Without this, item selection and stopping cannot be implemented coherently.

## Decision
Introduce a deterministic estimator layer:
- response contract
- estimate contract
- bounded MAP-style theta update
- information-derived SE

## Consequences
This is the estimator foundation, not the final calibrated production model.
It is good enough to:
- wire CAT layers end-to-end,
- validate monotonic behavior,
- support later replacement by calibrated estimation.

## Next
1. item information function
2. selector by max information near theta
3. stopping rule contract
