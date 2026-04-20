# Synthetic Session Harness — Stage 5 Validation
**Date:** 2026-04-20

---

## Pre-Run State
- vocab_attempts with completion_reason='question_limit_reached' (live): 21
- vocab_attempts with completion_reason='simulation_exhausted' (synthetic): 60
- mode_runs with source='synthetic_harness': 0

## Harness Run
Command: `python3 scripts/run_synthetic_vocab_sessions.py --profile all --n-sessions 2 --seed 42`

| attempt_id | profile | questions | correct | dk | source | completion_reason |
|-----------|---------|-----------|---------|-----|--------|-----------------|
| 1016 | strong | 24 | 22 (91.7%) | 0 | synthetic_harness | simulation_exhausted |
| 1017 | strong | 24 | 21 (87.5%) | 0 | synthetic_harness | simulation_exhausted |
| 1018 | medium | 24 | 12 (50.0%) | 2 | synthetic_harness | simulation_exhausted |
| 1019 | medium | 24 | 12 (50.0%) | 1 | synthetic_harness | simulation_exhausted |
| 1020 | weak | 24 | 6 (25.0%) | 1 | synthetic_harness | simulation_exhausted |
| 1021 | weak | 24 | 5 (20.8%) | 1 | synthetic_harness | simulation_exhausted |
| 1022 | dont_know_heavy | 24 | 9 (37.5%) | 13 | synthetic_harness | simulation_exhausted |
| 1023 | dont_know_heavy | 24 | 3 (12.5%) | 12 | synthetic_harness | simulation_exhausted |

## Post-Run State
- vocab_attempts with completion_reason='question_limit_reached' (live): **21 — unchanged**
- vocab_attempts with completion_reason='simulation_exhausted' (synthetic): 68 (+8)
- mode_runs with source='synthetic_harness': **8 (new)**

## Monitoring Exclusion Proof
Ran `python3 scripts/run_vocab_10k_monitoring.py` after harness run.
- Total real sessions: **21** (identical to pre-run)
- Distinct real users: **2** (identical to pre-run)
- Global status: INSUFFICIENT_DATA (unchanged)

**Synthetic sessions are invisible to monitoring: CONFIRMED**

## Test Results
- `test_synthetic_session_harness.py`: 20/20 PASS
- `test_monitoring_status_snapshot.py`: 10/10 PASS

## Synthetic Marker Design
| Marker | Column | Value | When set |
|--------|--------|-------|---------|
| Primary | `mode_runs.source` | `synthetic_harness` | Creation time |
| Secondary | `vocab_attempts.completion_reason` | `simulation_exhausted` | Finish time |

Both markers exclude the session from `REAL_SESSION_FILTER = "status = 'finished' AND completion_reason = 'question_limit_reached'"`.

No tranche-gate decision can be contaminated by synthetic sessions.
