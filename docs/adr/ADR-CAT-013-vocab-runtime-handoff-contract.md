# ADR-CAT-013 — Vocab runtime handoff contract

## Status
Accepted

## Goal
Define the first explicit contract for handing a real vocab runtime attempt into the CAT bridge.

## Surface
- `CATVocabHandoff`
- `build_vocab_cat_handoff(...)`
- `start_vocab_cat_handoff(...)`
- `answer_vocab_cat_handoff(...)`

## Canonical rules
- handoff is deterministic and stateless
- handoff builds stable CAT session id from user_id + mode + attempt_id
- handoff keeps original vocab attempt id in metadata
- handoff start delegates to layer 12 bridge start
- handoff answer delegates to layer 12 bridge answer
- handoff itself does not mutate legacy vocab runtime; it only defines the bridge boundary

## Next
Next layer should wire this contract into actual vocab runtime decision points.
