# ADR-CAT-035 — Rollout readiness

## Status
Accepted

## Goal
Freeze the final acceptance point at which CAT integration is considered implemented for the live vocab_v2 path.

## Surface
- `tests/unit/test_cat_rollout_readiness_contract.py`

## Acceptance criteria
- CAT runtime exposes native payload surface
- handler layer consumes runtime-native payloads
- `handlers/vocab_v2.py` preserves end-to-end runtime-native markers
- UI treats runtime-native payload as source of truth
- visible question and result shapes are CAT-native in the live vocab_v2 path

## Result
After this layer, CAT integration is considered complete at code/contract level.
The next step is manual staging smoke under feature flag, not more architectural layering.
