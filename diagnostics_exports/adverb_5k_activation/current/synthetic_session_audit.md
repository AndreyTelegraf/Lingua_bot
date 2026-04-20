# Synthetic Session Harness — Stage 1 Audit
**Date:** 2026-04-20
**Anchor commit:** 5bf11aa

---

## Schema

### `mode_runs`
- PK: `id INTEGER`
- `source TEXT` — nullable, currently only value is `'runtime_smoke'` (1 row). Ideal synthetic marker column.
- `completion_reason TEXT` — set at session end

### `vocab_attempts`
- PK: `id INTEGER`
- FK: `mode_run_id INTEGER → mode_runs.id` (NOT NULL, UNIQUE)
- FK: `user_id INTEGER → users.id`
- `status TEXT` — `started` / `finished`
- `completion_reason TEXT` — existing values: `NULL` (71 rows, started), `question_limit_reached` (21 rows, real live), `simulation_exhausted` (60 rows, old synthetic)

### `vocab_answers`
- FK: `attempt_id → vocab_attempts.id`
- `is_correct INTEGER`
- `answer_status TEXT`
- Monitoring signals (S1–S4) are computed from this table, NOT from `vocab_attempt_events`

### `vocab_attempt_events`
- Used by selector (`get_next_item`) to track shown items
- Written by `services/vocab_runtime/repo.py:log_event()`
- Does NOT drive monitoring signals directly

### `users`
- `is_bot INTEGER DEFAULT 0`
- `telegram_user_id INTEGER UNIQUE`

---

## Existing Synthetic Marker Situation

**PROVISIONAL label**: The current `REAL_SESSION_FILTER_NOTE` in `noun10k_monitoring_runner.py` says:
> "PROVISIONAL: 'question_limit_reached' set only by modes/vocab/router.py:332"

This is because there was no explicit `is_synthetic` marker — the exclusion relied on `simulation_exhausted` being an implicit signal. The 60 existing `simulation_exhausted` rows were inserted by a previous simulation harness but there is no live Python source that sets this value.

**Post-this-workstream**: The harness will set BOTH explicit markers:
1. `mode_runs.source = 'synthetic_harness'` (creation-time, on mode_runs)
2. `vocab_attempts.completion_reason = 'simulation_exhausted'` (completion-time, on vocab_attempts)

The PROVISIONAL label can be dropped.

---

## Code Path for Session Creation

**Sync path used by harness** (`services/vocab_runtime/`):
1. `INSERT INTO mode_runs (mode, user_id, status, source) VALUES ('vocab', ?, 'started', 'synthetic_harness')`
2. `services/vocab_runtime/repo.py:start_attempt(conn, user_id=..., mode_run_id=<int id from step 1>)`
   → inserts `vocab_attempts`
3. `services/vocab_runtime/selector.py:get_next_item(conn, attempt_id=...)` — reads `vocab_attempt_events`, no `vocab_selector_state` dependency
4. `services/vocab_runtime/repo.py:log_event(conn, ..., event_type='shown')` — writes `vocab_attempt_events`
5. `log_event(conn, ..., event_type='answer', is_correct=...)` — writes `vocab_attempt_events`, bumps `vocab_attempts` counters
6. **Direct INSERT INTO vocab_answers** — required because monitoring queries join this table (not `vocab_attempt_events`). `log_event` does NOT write `vocab_answers` in the sync path.
7. `services/vocab_runtime/repo.py:finish_attempt(conn, ..., completion_reason='simulation_exhausted')`

---

## Synthetic User Strategy

- `telegram_user_id` in range 9_000_001–9_999_999 (reserved range)
- `is_bot = 1`
- One synthetic user per profile, or one shared synthetic user per run

---

## Monitoring Exclusion

The current filter:
```
status = 'finished' AND completion_reason = 'question_limit_reached'
```
Already excludes `simulation_exhausted` sessions. No SQL filter change required.

After this workstream, the exclusion is explicit by design:
- Synthetic sessions have `completion_reason = 'simulation_exhausted'` → excluded by current filter
- Synthetic sessions have `mode_runs.source = 'synthetic_harness'` → additional belt-and-suspenders marker

The PROVISIONAL note on the filter should be updated to reflect this explicit design.

---

## Decision

**Synthetic marker**: `mode_runs.source = 'synthetic_harness'` + `completion_reason = 'simulation_exhausted'`
**Schema migration required**: NO — both columns already exist
**Monitoring SQL change required**: NO — current filter already excludes synthetic
**Comment update required**: YES — drop PROVISIONAL label, document explicit design
