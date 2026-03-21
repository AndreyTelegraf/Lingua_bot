# ADR-CAT-031 — UI consumes runtime-native payload

## Status
Accepted

## Goal
Make `bot/common_handlers/vocab_v2.py` consume `runtime_native_payload` as the source of truth for CAT-visible rendering, instead of inferring CAT question/result semantics from legacy-shaped fields.

## Surface
- `_runtime_native_payload(...)`
- `_apply_runtime_native_payload(...)`
- updated `_attach_ui_render(...)`

## Canonical rules
- UI trusts `runtime_native_payload.kind` when present
- CAT question rendering uses runtime `prompt_text`
- CAT result rendering may include runtime `stop_reason`
- legacy fallback remains intact when runtime-native payload is absent

## Next
Next layer should push runtime-native payload through `handlers/vocab_v2.py` and common-handler/router path without relying on decorative fallback logic.
