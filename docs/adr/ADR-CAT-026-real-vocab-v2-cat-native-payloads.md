# ADR-CAT-026 — Real vocab_v2 CAT-native payloads

## Status
Accepted

## Goal
Move the live `bot/common_handlers/vocab_v2.py` CAT branch one step beyond a generic prefix and into explicit CAT-native question/result/message payload semantics.

## Surface
- `_detect_cat_payload_kind(...)`
- `_build_cat_question_text(...)`
- `_build_cat_result_text(...)`
- `_build_cat_message_text(...)`
- updated `_build_cat_visible_payload(...)`
- updated `_build_legacy_visible_payload(...)`
- updated `_cat_info_payload(...)`

## Canonical rules
- CAT UI payloads expose explicit `cat_payload_kind`
- CAT UI payloads expose explicit `cat_native=True`
- CAT question and result rendering diverge visibly
- legacy payloads remain structurally intact and marked `cat_native=False`
- this layer still reuses legacy-shaped source payloads, but the bot-facing render contract is now CAT-native

## Next
Next layer should push CAT-native question/result structure deeper into runtime/handler payload generation so the UI stops inferring semantics from legacy payload shape.
