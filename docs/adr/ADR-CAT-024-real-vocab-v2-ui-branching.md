# ADR-CAT-024 — Real vocab_v2 UI branching

## Status
Accepted

## Goal
Patch the live `bot/common_handlers/vocab_v2.py` bot-facing layer so CAT and legacy paths already diverge in visible rendering, not only in hidden metadata.

## Surface
- `_decorate_text_for_branch(...)`
- `_attach_ui_render(...)`
- updated `run_vocab_v2_start_ui(...)`
- updated `run_vocab_v2_callback_ui(...)`

## Canonical rules
- UI branch remains additive and reversible
- legacy rendering is preserved byte-for-byte
- CAT rendering is explicitly marked at bot-facing layer
- router keeps existing aiogram flow intact

## Next
Next layer should patch the deeper handler/runtime payload shape so CAT path can render its own question/result semantics, not just a prefixed text.
