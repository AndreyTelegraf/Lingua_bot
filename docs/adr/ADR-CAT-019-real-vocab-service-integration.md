# ADR-CAT-019 — Real vocab service integration seam

## Status
Accepted

## Goal
Patch the real vocab service layer with an explicit CAT integration seam so production code has a direct service-level entry point for CAT start and answer routing.

## Surface
- `maybe_start_cat_from_vocab_service(...)`
- `maybe_continue_cat_from_vocab_service_answer(...)`

## Canonical rules
- service seam is thin and delegates to layer-18 production seam
- service seam returns explicit legacy vs cat routing result
- service seam is additive and does not yet delete legacy path
- this is the first real patch inside `services/vocab_runtime/service.py`

## Next
Next layer should patch concrete start/answer runtime call sites or FSM handlers to use this service seam in the actual production flow.
