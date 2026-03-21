# ADR-CAT-029 — Runtime-native payload core

## Status
Accepted

## Goal
Move CAT payload semantics into `services/cat_runtime/runtime.py` so question/result kind is emitted by runtime as the source of truth, instead of being inferred later from legacy-shaped payloads.

## Surface
- `CATRuntimeNativePayload`
- `CATRuntimeStartResult`
- `CATRuntimeAnswerResult`
- `build_cat_runtime_native_payload(...)`
- `start_cat_session_runtime_native(...)`
- `answer_cat_session_runtime_native(...)`

## Canonical rules
- runtime emits explicit `kind=question|result|message`
- runtime emits explicit `mode`, `session_id`, `status`, `theta`, `se`
- question payload carries `item_id`, `prompt_text`, `answer_key`
- result payload carries `stop_reason`
- legacy runtime surface remains intact; native payload surface is additive

## Next
Next layer should make vocab-facing handler/service path consume runtime-native payloads directly instead of reconstructing CAT semantics from branch metadata.
