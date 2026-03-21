# ADR-CAT-034 — Staging smoke contract

## Status
Accepted

## Goal
Freeze a staging-oriented smoke contract for the live CAT path so final rollout readiness is checked against the assembled runtime-native chain, not against isolated lower-level units.

## Surface
- `tests/unit/test_cat_staging_smoke_contract.py`

## Canonical rules
- handler layer must expose runtime-native normalized fields
- `handlers/vocab_v2.py` must preserve e2e runtime-native markers
- `bot/common_handlers/vocab_v2.py` must render from runtime-native payload as source of truth
- question and result smoke shapes must both be validated
- this layer is rollout-oriented validation, not a new abstraction layer

## Next
Next layer should freeze final rollout-readiness and define the exact point at which CAT integration is considered complete.
