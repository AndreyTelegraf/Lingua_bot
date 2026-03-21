# ADR-CAT-011 — Repo-backed runtime start/answer contract

## Status
Accepted

## Goal
Wire CAT runtime start/answer flows to the repo-backed bank loader so runtime can operate without an externally supplied in-memory bank.

## Surface
- `start_cat_session_runtime(..., item_bank=None, active_only=True, limit=None)`
- `answer_cat_session_runtime(..., item_bank=None, active_only=True, limit=None)`

## Canonical rules
- if `item_bank` is passed, runtime uses it as before
- if `item_bank` is omitted, runtime loads CAT items from `vocab_items` through layer 10
- empty loaded bank is a hard error
- runtime event contract from layer 8 remains unchanged
- this layer still uses the full loaded bank per call; no cached bank/session snapshot yet

## Next
Next layer should add session snapshot / planned-item persistence so answer flow can validate that the answered item matches the last planned CAT item.
