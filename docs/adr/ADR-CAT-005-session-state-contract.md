# ADR-CAT-005 — CAT session state contract

## Status
Accepted

## Context
CAT now has:
- item model
- estimator
- selector
- stopping rule

A stable session state contract is required before loop orchestration.

## Decision
Introduce:
- CATSessionAnswer
- CATSessionState
- create_cat_session(...)
- append_answer(...)
- finish_cat_session(...)
- serialize_cat_session(...)
- restore_cat_session(...)

Session state stores:
- session identity
- modality
- current theta / se
- administered item ids
- answer history with before/after estimate snapshots
- lifecycle status
- metadata

## Consequences
This becomes the canonical in-memory/session payload for future CAT orchestration and persistence layers.

## Next
1. CAT loop orchestration contract
2. CAT persistence/repo contract
3. CAT integration into runtime modes
