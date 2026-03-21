# ADR-CAT-025 — Real vocab_v2 CAT visible rendering

## Status
Accepted

## Goal
Make the live `bot/common_handlers/vocab_v2.py` CAT path visibly distinct not only by prefix, but by explicit render semantics and CAT-specific affordance.

## Surface
- `_decorate_keyboard_for_branch(...)`
- `_build_cat_visible_payload(...)`
- `_build_legacy_visible_payload(...)`
- `_cat_info_payload(...)`
- updated `_attach_ui_render(...)`
- updated `build_vocab_v2_router()`

## Canonical rules
- CAT visible path exposes explicit `visible_mode=cat`
- CAT visible path exposes explicit `visible_semantics=adaptive`
- CAT visible path prepends CAT info affordance into keyboard
- legacy visible path remains structurally unchanged
- UI divergence is still additive and reversible

## Next
Next layer should move from generic CAT-labelled text to real CAT-native question/result payloads coming from runtime, instead of decorating legacy-shaped payloads.
