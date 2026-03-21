# ADR-CAT-023 — Real vocab_v2 common-handler branching

## Status
Accepted

## Goal
Patch the real `bot/common_handlers/vocab_v2.py` layer so the live bot-facing vocab_v2 path carries explicit UI/runtime branch metadata (`legacy|cat`).

## Surface
- `run_vocab_v2_start_ui(...)`
- `run_vocab_v2_callback_ui(...)`
- updated `build_vocab_v2_router()`

## Canonical rules
- common handler keeps existing aiogram behavior intact
- handler is additive: visible UX is unchanged
- common handler normalizes `runtime_branch`
- common handler adds `ui_branch`
- `ui_branch=cat` only when runtime branch is already `cat`

## Next
Next layer should patch the visible bot response/rendering path to actually diverge when `ui_branch == "cat"`.
