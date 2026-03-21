# ADR-CAT-027 — Handler-layer CAT-native payloads

## Status
Accepted

## Goal
Push CAT-native payload semantics one layer deeper, into `services/vocab_runtime/handler_layer.py`, so bot-facing UI no longer has to infer CAT question/result/message type from legacy-shaped payloads on its own.

## Surface
- `_detect_cat_payload_kind_from_handler(...)`
- `_attach_cat_native_payload_from_handler(...)`
- wrapped `handle_vocab_start(...)`
- wrapped `handle_vocab_callback(...)`

## Canonical rules
- handler layer emits explicit `cat_payload_kind`
- handler layer emits explicit `cat_native`
- CAT branch emits explicit `visible_mode=cat`
- CAT branch emits explicit `visible_semantics=adaptive`
- legacy branch remains additive and marked `cat_native=False`

## Next
Next layer should simplify `bot/common_handlers/vocab_v2.py` so it trusts handler/runtime payload semantics instead of inferring CAT shape from legacy fields such as `finished` and `keyboard`.
