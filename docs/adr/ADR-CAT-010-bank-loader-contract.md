# ADR-CAT-010 — Repo-backed bank loader / eligibility contract

## Status
Accepted

## Goal
Introduce a repo-backed CAT bank loading layer that reads real vocab rows from storage and converts only eligible rows into canonical CAT items.

## Surface
- `CATBankLoadStats`
- `load_vocab_rows_for_cat(conn, ...)`
- `summarize_vocab_rows_eligibility(rows, ...)`
- `load_cat_item_bank_from_vocab(conn, ...)`

## Canonical rules
- loader reads from `vocab_items`
- loader itself is DB-backed, adapter remains pure
- eligibility is deterministic
- inactive rows may be filtered
- rows with no prompt source and no answer are excluded
- explicit `difficulty_b` is preserved and mapping is delegated to layer 9 adapter

## Next
Next layer should wire runtime start/answer flows to repo-backed bank loading instead of requiring external in-memory item bank.
