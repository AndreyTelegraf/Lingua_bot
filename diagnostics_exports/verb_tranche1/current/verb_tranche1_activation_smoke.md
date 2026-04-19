# Verb Tranche1 — Activation Smoke Report

**Date:** 2026-04-19
**DB:** data/lingua_staging.db (post-activation state)

## Tests Run

| Test Suite | Tests | Result | Notes |
|------------|-------|--------|-------|
| `test_vocab_bank_qa_contract` — correct_choice_count | 1 | PASS | All active items have exactly 1 correct choice |
| `test_vocab_bank_qa_contract` — no_dup_lemma_pos | 1 | PASS | No dup lemma/pos pairs introduced |
| `test_vocab_bank_qa_contract` — no_orphan_choices | 1 | PASS | No orphaned vocab_choices rows |
| `test_vocab_bank_qa_contract` — exactly_6_choices | 1 | PRE-EXISTING FAIL | 12 noun items (IDs 10729–10769) have 4 choices; identical in backup DB; not caused by verb activation |
| `test_distractor_contract_v1_1` | 1 | PASS | |
| `test_apply_distractor_contract_v1_rebuild` | 1 | PASS | |
| `test_noun10k_monitoring_runner` | 26 | PASS | noun/10K monitoring unaffected |
| `test_vocab_qa_router` | 3 | PASS | |
| `test_vocab_selector_*` | — | SKIP (pre-existing env: missing `aiosqlite`) | Not caused by this activation |
| `test_vocab_metadata_schema_contract` | — | SKIP (pre-existing: hardcoded Linux path) | Not caused by this activation |

**Total runnable: 34 passed, 0 new failures**

## Bank QA Script Results

- Active items: 818 ✓
- Dup lemmas: junto (2), rosa (2), rápido (2) — all pre-existing, none are verb tranche1 items
- Dup question_text: pre-existing pattern (Что значит это слово? generics)

## Pre-Existing Failures (not caused by this activation)

1. **6-choice contract**: 12 noun items (IDs 10729–10769, all 10K) have 4 choices instead of 6. Confirmed identical in pre-activation backup. Out of scope for this workstream.
2. **Metadata schema/values tests**: hardcoded path `/home/andrey/Projects/...` — wrong machine.
3. **Selector tests**: `aiosqlite` not installed in this environment.

All 3 failure classes confirmed pre-existing by comparison against `data/lingua_staging_preactivation_20260419_103602.db`.

## Our Items: All Clean

- 9 activated verb items: 6 choices each ✓, 1 correct choice ✓, no orphans ✓, no dup lemmas ✓
