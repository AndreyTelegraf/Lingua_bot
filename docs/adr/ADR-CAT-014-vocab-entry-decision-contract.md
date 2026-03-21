# ADR-CAT-014 — Vocab entry decision / start wiring contract

## Status
Accepted

## Goal
Define the first explicit entry-point contract at the vocab runtime boundary: decide whether CAT should be used, build stable handoff payload, and optionally start CAT runtime.

## Surface
- `CATVocabEntryDecision`
- `CATVocabEntryStartResult`
- `decide_vocab_cat_entry(...)`
- `start_vocab_runtime_cat_entry(...)`

## Canonical rules
- decision is feature-gated
- decision is deterministic for the same user_id + attempt_id + mode
- if CAT is disabled, entry returns an explicit noop result
- if CAT is enabled, entry delegates startup to layer 13 handoff
- this layer only defines start-path wiring at vocab boundary
- legacy vocab runtime remains untouched; no forced replacement yet

## Next
Next layer should wire answer-path routing at the same boundary, so vocab runtime can continue an already-started CAT session through one stable integration surface.
