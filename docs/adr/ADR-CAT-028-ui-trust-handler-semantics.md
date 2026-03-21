# ADR-CAT-028 — UI trusts handler-layer CAT semantics

## Status
Accepted

## Goal
Simplify `bot/common_handlers/vocab_v2.py` so it stops inferring CAT semantics from legacy-shaped clues and instead trusts the normalized CAT-native fields already emitted by `services/vocab_runtime/handler_layer.py`.

## Surface
- updated `_attach_ui_render(...)`
- updated CAT/legacy visible builders
- UI now reads:
  - `runtime_branch`
  - `visible_mode`
  - `visible_semantics`
  - `cat_payload_kind`
  - `cat_native`

## Canonical rules
- UI trusts handler semantics as source of truth
- CAT question/result rendering is selected from `cat_payload_kind`
- legacy path remains untouched
- keyboard CAT affordance stays additive and reversible

## Next
Next layer should push CAT-native payload structure below handler layer into service/flow/runtime payload generation so handler stops being the first semantic normalization point.
