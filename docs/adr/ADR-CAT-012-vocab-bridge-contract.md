# ADR-CAT-012 — Feature-gated mode bridge contract

## Status
Accepted

## Goal
Add the first thin bridge between real mode/runtime flows and CAT runtime, without yet replacing the existing non-CAT path.

## Surface
- `CATBridgeDecision`
- `cat_feature_enabled(flag_value)`
- `should_use_cat_for_mode(mode=..., feature_enabled=...)`
- `build_cat_session_id(user_id=..., mode=..., attempt_id=...)`
- `start_mode_cat_bridge(...)`
- `answer_mode_cat_bridge(...)`

## Canonical rules
- bridge is feature-gated
- bridge support is mode-scoped, initially only `vocab`
- session id is deterministic and stable across start/answer transitions
- bridge delegates actual CAT work to repo-backed CAT runtime from layer 11
- bridge does not yet replace existing vocab runtime; it only defines the contract for safe wiring

## Next
Next layer should define a real vocab-runtime handoff contract: when CAT path is chosen, how current vocab attempt/session state maps into CAT bridge start/answer calls.
