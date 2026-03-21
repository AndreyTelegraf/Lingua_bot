# ADR-CAT-008 — Runtime integration contract

## Status
Accepted

## Goal
Define the first runtime-facing CAT layer that wires together canonical session state, orchestration, persistence, and append-only runtime events.

## Surface
- `CATStartResult`
- `start_cat_session_runtime(conn, session_id=..., user_id=..., modality=..., item_bank=...)`
- `answer_cat_session_runtime(conn, session_id=..., item=..., response_value=..., is_correct=..., item_bank=...)`
- `load_cat_session_runtime(conn, session_id=...)`

## Canonical rules
- runtime start persists session immediately
- runtime start appends `session_started`
- runtime start then plans first step and appends either `item_planned` or `session_stopped`
- runtime answer loads canonical session, records answer via orchestration, persists session, and appends `answer_recorded`
- the next transition is appended as `item_planned` or `session_stopped`
- this layer uses provided in-memory CAT item bank only; no real vocab bank adapter yet

## Next
Next layer should introduce bank adapter / mapper contract from real vocab items into CAT item models.
