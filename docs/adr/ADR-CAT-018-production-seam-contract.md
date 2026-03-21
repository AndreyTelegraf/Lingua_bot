# ADR-CAT-018 — Production seam / real vocab runtime patch contract

## Status
Accepted

## Goal
Define the final narrow production seam that real vocab runtime code can call directly, without knowing internal CAT bridge/router details.

## Surface
- `CATVocabPatchedStart`
- `CATVocabPatchedAnswer`
- `patchable_start_from_vocab_runtime(...)`
- `patchable_answer_from_vocab_runtime(...)`

## Canonical rules
- production seam stays feature-gated through prior layers
- seam returns explicit `legacy` vs `cat`
- seam is thin and delegates to layer-17 FSM wiring
- seam is the intended call point for actual runtime/handler patching
- no legacy vocab mutation is introduced beyond existing CAT side effects

## Next
Next step is not another CAT contract layer. Next step is real patching of actual vocab runtime / handlers to call this seam in production code, followed by staging smoke.
