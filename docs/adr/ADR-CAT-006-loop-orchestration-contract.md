# ADR-CAT-006 — Loop orchestration contract

## Status
Accepted

## Goal
Define a thin orchestration layer for CAT runtime that:
- derives the current estimate from session state
- evaluates stopping rule before item selection
- excludes already administered items
- selects the next item from the remaining pool
- records an answer, re-estimates theta, and plans the next step

## Session contract used
Session state is canonicalized by layer 5:
- `theta` and `se` live directly on `CATSessionState`
- there is no `current_estimate` field
- session active status is `in_progress`
- session completion is represented through `finish_cat_session(...)`

## Orchestration surface
- `CATOrchestrationStep`
- `plan_next_cat_step(session, candidate_items=...)`
- `record_answer_and_plan_next(session, item=..., response_value=..., is_correct=..., item_bank=...)`

## Policy
- stopping rule runs before selection
- administered items are excluded
- if pool is exhausted, session stops with `item_bank_exhausted`
- selector receives `estimate=...`, not raw `theta=...`
