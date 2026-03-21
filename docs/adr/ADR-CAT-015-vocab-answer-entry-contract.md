# ADR-CAT-015 — Vocab answer entry / continuation contract

## Status
Accepted

## Goal
Define the first explicit answer-path entry contract at the vocab runtime boundary, so an already-started CAT session can be continued through one stable integration surface.

## Surface
- `CATVocabAnswerDecision`
- `decide_vocab_cat_answer(...)`
- `continue_vocab_runtime_cat_entry(...)`

## Canonical rules
- answer-path decision is deterministic for the same user_id + attempt_id + mode
- disabled CAT path returns explicit noop decision/result
- continuation requires a stable handoff/session id derived from user_id + mode + attempt_id
- continuation delegates to layer 13 handoff answer-path
- this layer only defines answer-path routing at vocab boundary
- legacy vocab runtime remains untouched; no forced replacement yet

## Next
Next layer should wire start+answer CAT entry surfaces into the actual vocab runtime decision points / FSM path.
