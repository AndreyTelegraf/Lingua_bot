# ADR-CAT-020 — Real service entrypoints contract

## Status
Accepted

## Goal
Patch the real `services/vocab_runtime/service.py` entrypoints that are actually used by vocab runtime flows.

## Surface
- wrapped `start_or_resume_attempt(...)`
- wrapped `get_next_question(...)`
- wrapped `submit_answer(...)`
- wrapped `submit_choice(...)`

## Canonical rules
- original legacy behavior is preserved through `_..._legacy(...)`
- CAT side effects are additive
- disabled CAT path is strict noop
- wrapper returns legacy result, optionally enriched with `cat_route`

## Next
Next layer should patch the concrete bot/FSM handlers to inspect `cat_route` and choose visible CAT vs legacy behavior in the real user flow.
