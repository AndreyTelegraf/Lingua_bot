# ADR-CAT-022 — Real vocab_v2 handler branching

## Status
Accepted

## Goal
Patch the real `handlers/vocab_v2.py` layer so the live vocab_v2 path carries explicit runtime branch metadata (`legacy|cat`) to the bot-facing layer.

## Surface
- `vocab_v2_start(...)`
- `vocab_v2_callback(...)`

## Canonical rules
- handler keeps existing FSM-store behavior intact
- handler is additive: legacy output is preserved
- handler adds `runtime_branch`
- `runtime_branch=cat` only when `cat_route.source == "cat"`

## Next
Next layer should patch `bot/common_handlers/vocab_v2.py` to optionally react differently when `runtime_branch == "cat"`.
