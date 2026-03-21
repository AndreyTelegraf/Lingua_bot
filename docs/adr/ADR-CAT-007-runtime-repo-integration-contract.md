# ADR-CAT-007 — Runtime/repo integration contract

## Status
Accepted

## Goal
Define the persistence contract for CAT runtime state so the adaptive loop can survive restarts and be wired into real bot/runtime flows.

## Scope
This layer adds:
- CAT session persistence table contract
- CAT event log table contract
- save/load roundtrip for canonical session state
- append/list event helpers for orchestration/audit

## Canonical rules
- session payload is stored as canonical serialized JSON from layer 5
- session row is upserted by `session_id`
- event log is append-only
- session status in storage mirrors canonical session state status
- this layer does not yet wire CAT into vocab runtime; it only defines durable persistence surface

## Surface
- `ensure_cat_runtime_tables(conn)`
- `save_cat_session(conn, session)`
- `load_cat_session(conn, session_id=...)`
- `append_cat_session_event(conn, session_id=..., event_type=..., payload=...)`
- `list_cat_session_events(conn, session_id=...)`

## Next
Next layer will wire orchestration + repo into a runtime integration contract with concrete start/load/save/answer transitions.
