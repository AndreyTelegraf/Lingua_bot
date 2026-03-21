# ADR-CAT-033 — UI strictly prefers runtime-native payload

## Status
Accepted

## Goal
Make `bot/common_handlers/vocab_v2.py` treat `runtime_native_payload` as the single source of truth whenever it is present.

## Surface
- `_payload_prefers_runtime_native(...)`
- `_coerce_native_question_text(...)`
- `_coerce_native_result_text(...)`
- updated `_apply_runtime_native_payload(...)`
- updated `_attach_ui_render(...)`

## Canonical rules
- runtime-native payload has absolute priority over legacy-shaped fields
- `kind` from runtime-native payload wins over `finished`, `keyboard`, `cat_payload_kind`
- legacy fallback remains only for callers that do not provide runtime-native payload
- UI keeps backward compatibility for non-native callers

## Next
Next layer should perform final staging-oriented CAT smoke/integration validation on the live vocab_v2 path under feature flag.
