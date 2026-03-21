# ADR-CAT-009 — Bank adapter / mapper contract

## Status
Accepted

## Goal
Define a deterministic adapter layer that maps real vocab-bank rows into canonical `CATItemModel` objects.

## Surface
- `CATBankAdapterStats`
- `map_vocab_row_to_cat_item(row, ...)`
- `map_vocab_rows_to_cat_items(rows, ...)`
- `summarize_vocab_rows_adapter(rows, ...)`

## Canonical rules
- adapter is pure and deterministic
- active-only filtering is handled here
- explicit `difficulty_b` wins over derived difficulty
- when `difficulty_b` is absent, a coarse fallback may be derived from `freq_rank`
- adapter does not query DB; it only maps provided rows
- adapter does not yet decide CAT eligibility policy beyond shape normalization

## Next
Next layer should add repo-backed bank loader / eligibility contract from real storage.
