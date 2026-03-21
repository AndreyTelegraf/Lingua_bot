# ADR-CAT-017 — Vocab FSM wiring contract

## Status
Accepted

## Goal
Define the first explicit CAT wiring surface intended for real vocab runtime / FSM decision points, while still keeping legacy flow intact.

## Surface
- `CATVocabFSMStartRoute`
- `CATVocabFSMAnswerRoute`
- `maybe_start_cat_from_vocab_attempt(...)`
- `maybe_continue_cat_from_vocab_attempt_answer(...)`

## Canonical rules
- wiring surface is feature-gated through layer 16 router
- explicit `legacy` vs `cat` source is returned
- start-path and answer-path are both exposed in runtime/FSM-friendly form
- no legacy vocab mutation is introduced here beyond CAT side effects already defined in prior layers
- this layer is the intended seam for patching real handlers / FSM branches

## Next
Next layer should patch actual vocab runtime/FSM entry points to call this wiring surface and choose legacy vs CAT path in production code.
