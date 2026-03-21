# ADR-CAT-032 — Vocab v2 E2E runtime-native contract

## Status
Accepted

## Goal
Verify that CAT runtime-native payload reaches the live vocab_v2 path end-to-end without being reconstructed from legacy-shaped fields.

## Surface
- `handlers/vocab_v2.py`
- `_attach_e2e_runtime_native_payload(...)`
- `tests/unit/test_vocab_v2_e2e_runtime_native_contract.py`

## Canonical rules
- runtime-native payload must survive through `handle_vocab_start(...)` into `vocab_v2_start(...)`
- runtime-native payload must survive through `handle_vocab_callback(...)` into `vocab_v2_callback(...)`
- live vocab_v2 path exposes explicit `e2e_runtime_native`
- live vocab_v2 path exposes explicit `e2e_payload_kind`
- legacy callers remain supported

## Next
Next layer should remove remaining UI-side fallback inference where runtime-native payload is already present and make real rendering trust only source-of-truth CAT payload semantics.
