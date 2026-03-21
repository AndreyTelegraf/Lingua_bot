# ADR-CAT-030 — Handler layer consumes runtime-native payload

## Status
Accepted

## Goal
Make `services/vocab_runtime/handler_layer.py` consume CAT runtime-native payloads as the source of truth instead of reconstructing CAT semantics from scattered legacy-shaped fields.

## Surface
- `_runtime_payload_to_handler_fields(...)`
- updated `_attach_cat_native_payload_from_handler(...)`
- wrapped `handle_vocab_start(...)`
- wrapped `handle_vocab_callback(...)`

## Canonical rules
- handler layer trusts `payload.kind` from CAT runtime
- handler layer emits `runtime_native_payload` as normalized dict
- handler layer derives `cat_payload_kind` from runtime-native payload when present
- legacy fallback remains intact for non-CAT and pre-native payload callers

## Next
Next layer should simplify `bot/common_handlers/vocab_v2.py` to read `runtime_native_payload` directly and stop reconstructing CAT-visible semantics on its own.
