# ADR-CAT-016 — Vocab runtime router contract

## Status
Accepted

## Goal
Define one stable CAT routing surface for vocab runtime so start-path and answer-path decisions can be called through a single contract before wiring into real FSM/runtime points.

## Surface
- `CATVocabRuntimeRouteResult`
- `route_vocab_runtime_cat_start(...)`
- `route_vocab_runtime_cat_answer(...)`

## Canonical rules
- router is feature-gated through layers 14 and 15
- router does not replace legacy vocab runtime yet
- router returns explicit noop result when CAT path is not selected
- start-path delegates to layer 14 entry surface
- answer-path delegates to layer 15 answer-entry surface
- router keeps side effects inside CAT runtime only

## Next
Next layer should patch real vocab runtime decision points / FSM handlers to call this router and choose between legacy and CAT path explicitly.
