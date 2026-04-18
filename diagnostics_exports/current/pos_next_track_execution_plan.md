# Verb Next-Track Execution Plan

**Date:** 2026-04-18
**POS:** verb
**Decision basis:** `pos_next_track_decision.md`
**Mode:** Measurement-first. No activation until real-signal gates are met.

---

## Scope constraints (hard)

- This plan covers verbs only.
- Adverbs are explicitly out of scope.
- noun/10K must not be touched (tranche2 is inactive; monitoring is in accumulation phase).
- No selector or runtime changes.
- No production writes.
- Staging only.
- One stage = one commit, only if acceptance is green.

---

## Stage A — Audit / Preflight

**Goal:** Establish ground truth on the inactive verb pool. Determine which items are activatable without new generation.

**Allowed changes:**
- Run existing `tools/run_verb_ru_gloss_audit.py` against staging DB (read-only audit mode).
- Export results to `diagnostics_exports/verb_tranche1/`.
- Write audit summary JSON.

**Non-goals:**
- Do not apply any decisions.
- Do not deactivate or activate any items.
- Do not generate new candidates.

**Required artifacts:**
- `diagnostics_exports/verb_tranche1/verb_gloss_audit_YYYYMMDD.jsonl`
- `diagnostics_exports/verb_tranche1/verb_gloss_review.csv`
- `diagnostics_exports/verb_tranche1/verb_gloss_summary.json`
- `diagnostics_exports/verb_tranche1/verb_preflight_counts.json` containing:
  - total inactive verbs audited
  - auto-reject count (risk >= 100)
  - review-required count
  - provisionally-pass count
  - breakdown by bin

**Acceptance checks:**
- Audit output exists and is non-empty.
- Count totals reconcile: auto_reject + review_required + provisionally_pass = total_audited.
- NULL-bin items (23) are flagged separately and excluded from tranche1 pipeline.

**Stop condition:** If provisionally_pass < 5 across 10K + 20K combined, stop and escalate — fresh generation required before tranche1 is viable.

**Commit allowed:** YES (after audit artifacts are complete and acceptance checks pass).

**Suggested commit message:** `"vocab: run verb inactive pool gloss audit for tranche1 preflight"`

---

## Stage B — Candidate Pool Assembly

**Goal:** From the provisionally-passing audit set, assemble the tranche1 candidate CSV.

**Allowed changes:**
- Write a candidate CSV: `diagnostics_exports/verb_tranche1/verb_tranche1_candidates.csv`
- Format: same schema as noun/10K tranche1 pipeline (candidate_id, lemma, pos, bin_name, cefr_target, correct_answer, distractor_1/2/3, judge_note, import_status, import_item_id, concept_group, topic_tag, collision_note)

**Non-goals:**
- Do not generate new candidates from Kaikki or external source in this stage.
- Do not import to DB.
- Do not change any item status.

**Prioritisation rules:**
1. Prefer 10K and 20K items first (address underrepresented bins relative to selector).
2. Within a bin, prefer items with `provisionally_pass` status from Stage A.
3. Exclude NULL-bin items.
4. Exclude any item with a hard auto-reject flag.
5. If total passing items in 10K+20K < 5: flag and note, but continue with available items — do not silently pad from lower bins.

**Required artifacts:**
- `diagnostics_exports/verb_tranche1/verb_tranche1_candidates.csv` (all provisionally-pass items, status=READY)
- `diagnostics_exports/verb_tranche1/verb_tranche1_pool_summary.json` (counts by bin, rejection reasons summary)

**Acceptance checks:**
- All candidate items have: lemma, correct_answer, 3 distractors, pos=verb, bin_name not NULL, cefr_target, import_item_id.
- No item in candidate CSV appears in auto-reject list.
- Candidate count is correct (matches provisionally_pass total minus NULL-bin).

**Commit allowed:** YES (after pool assembly artifacts complete and acceptance checks pass).

---

## Stage C — Rule-Based Filtering / Collision Review

**Goal:** Apply Rule 1a + 1b collision checks against active verb bank and report hard blocks.

**This is an automated stage.** Use (or adapt) `scripts/noun10k_tranche2_prepare.py` as reference — the same anti-collision logic applies.

**Allowed changes:**
- Run collision check (read-only DB access).
- Write collision report: `diagnostics_exports/verb_tranche1/verb_tranche1_collision_report.json`

**Non-goals:**
- Do not fix collisions in this stage.
- Do not activate.
- Do not change any DB record.

**Rules to apply:**
- Rule 1a: new correct_answer must not be an active distractor in any active verb item.
- Rule 1b: no active verb correct_answer may appear as a distractor in any new candidate.
- Duplicate lemma check: new candidate lemma must not duplicate any active verb.
- Choice integrity check: all candidates must have exactly 1 correct_answer + 3 distractors.

**Required artifacts:**
- `diagnostics_exports/verb_tranche1/verb_tranche1_collision_report.json` containing:
  - remaining_pool_size (candidate count going in)
  - hard_blocked_count
  - hard_blocked items (with reasons)
  - eligible_count (remaining_pool_size - hard_blocked_count)
  - eligible items list

**Acceptance checks:**
- Count reconciliation: remaining_pool_size - hard_blocked_count = eligible_count.
- No hard-blocked items in the eligible set.

**Stop condition:** If eligible_count < 5, stop and report — not enough clean items for a meaningful tranche.

**Commit allowed:** YES (after collision report complete and reconciliation passes).

---

## Stage D — Tranche1 Prepare-Only Pack

**Goal:** Select the final tranche1 items. Produce import-ready artifacts. No activation.

**Selection rules (same as noun/10K tranche2):**
- Tranche size: up to 10 items (or all eligible if < 10).
- Max 2 items per concept_group.
- CLEAN items before WARN items.
- Intra-cluster conflict avoidance for WARN pairs.
- Priority: 10K and 20K items before lower bins (to address structural gaps).

**Allowed changes:**
- Write tranche1 manifest JSON.
- Write tranche1 manifest CSV.
- Write a DO-NOT-RUN apply script (chmod 644, not executable).

**Non-goals:**
- Do not run the apply script.
- Do not activate any items.
- Do not modify staging DB.

**Required artifacts:**
- `diagnostics_exports/verb_tranche1/verb_tranche1_manifest.json`
- `diagnostics_exports/verb_tranche1/verb_tranche1_manifest.csv`
- `diagnostics_exports/verb_tranche1/verb_tranche1_apply_DONOTRUN.sh` (chmod 644)

**Apply script must contain:**
- "DO NOT RUN" in first 5 lines
- "PREPARE ONLY" in first 5 lines
- "ACTIVATION IS NOT AUTHORIZED" in first 5 lines
- All `UPDATE vocab_items SET is_active=1` statements for selected items

**Acceptance checks:**
- Apply script exists, is NOT executable (mode & 0o111 == 0).
- Manifest selected_count matches selected items list length.
- Count reconciliation: eligible - selected = reserve.
- No selected item appears in hard_blocked list.
- Dry-run of apply script (bash -n) passes.

**Commit allowed:** YES (after all artifacts complete, apply script non-executable, dry-run passes).

**Suggested commit message:** `"vocab: prepare verb tranche1 pack (DO NOT ACTIVATE)"`

---

## Stage E — Monitoring Design

**Goal:** Define the monitoring runner for verb tranche1 — signals, triggers, and minimum sample gate.

**Allowed changes:**
- Write `scripts/verb_monitoring_runner.py` (read-only, same pattern as `noun10k_monitoring_runner.py`).
- Write monitoring plan: `diagnostics_exports/verb_tranche1/verb_tranche1_monitoring_plan.md`.
- Write unit tests: `tests/unit/test_verb_monitoring_runner.py`.

**Non-goals:**
- Do not activate items.
- Do not change selector or runtime.
- Do not run against staging until items are active.

**Signals to implement (adapt from noun/10K plan):**
- Signal 1: active verb items shown per complete real session (is_active=1 filter mandatory).
- Signal 2: per-item exposure counts across real sessions (is_active=1 filter).
- Signal 3: per-user repeat rate across consecutive sessions (is_active=1 filter).
- Signal 4: per-item correctness rate (min 5 answers, is_active=1 filter).

**Triggers:**
- T1 (REPEAT_SATURATION): mean_repeat_rate > 0.33
- T2 (POOL_DEPLETION): mean_items_per_session < 2.0 (verbs have higher target than nouns — 7/session)
- T3 (COVERAGE_FAILURE): fewer than 8 of selected items with sessions_shown >= 3
- T4 (EXPOSURE_SKEW): top item sessions_shown >= 8 while pool median < 3

**Minimum sample gate:**
- 30 complete sessions
- 3 distinct users
- 5 answers per item (for Signal 4)

**Required artifacts:**
- `scripts/verb_monitoring_runner.py`
- `tests/unit/test_verb_monitoring_runner.py` (≥20 tests, 100% pass)
- `diagnostics_exports/verb_tranche1/verb_tranche1_monitoring_plan.md`

**Acceptance checks:**
- All tests pass.
- Runner outputs `signal_scope_note` explaining is_active=1 filter.
- Runner is read-only (sqlite3 URI mode=ro).
- All 4 signals filter `vi.is_active = 1`.

**Commit allowed:** YES (after tests pass and monitoring plan written).

**Suggested commit message:** `"vocab: add verb tranche1 monitoring runner and plan"`

---

## Stage F — Activation Gate and Acceptance Rules

**This stage defines the conditions under which tranche1 activation is allowed.**
**Activation itself is NOT part of this plan.**

**Pre-activation requirements (all must be true):**

1. **Staging import completed:** All tranche1 items have been imported to staging with `is_active=0` by running the DO-NOT-RUN script manually.

2. **Post-import checks pass:** Verify item counts, choice counts, and integrity after import.

3. **Selector smoke test passes:** `python scripts/runtime_vocab_smoke.py` with verb tranche1 items in bank.

4. **Activation authorization:** A human operator reviews the tranche1 manifest and explicitly authorizes activation in writing.

5. **Activation is scoped to tranche1 only:** No other items are activated in the same operation.

**Activation conditions that justify tranche1 go-ahead:**
- All pre-activation requirements met.
- No hard-blocked items in the activation set.
- Staging import dry-run passes.
- No outstanding selector contract violations.

**Monitoring after activation:**
- Run `verb_monitoring_runner.py` after each batch of 10+ real sessions.
- Do NOT activate tranche2 until:
  - minimum sample gate is met (30 sessions / 3 users)
  - at least one of T1–T4 fires OR verdict is HOLD with ≥30 sessions confirmed
  - no INVESTIGATE_SIGNAL items (pct_correct < 20%)

**Forbidden until real-signal gates are met:**
- Activating tranche2 items
- Deactivating any tranche1 items based on heuristics alone
- Changing selector weights based on session observations
- Treating INSUFFICIENT_DATA verdict as a signal

---

## Summary Timeline

```
Stage A: verb gloss audit          → 1 commit
Stage B: candidate pool assembly   → 1 commit
Stage C: collision review          → 1 commit
Stage D: tranche1 prepare pack     → 1 commit
Stage E: monitoring design         → 1 commit
Stage F: activation gate           → manual human step (not a commit)
```

**Total planned commits:** 5
**Estimated activatable items:** Unknown until Stage A; expected 10–30 items from 10K+20K inactive pool.

---

## What Must Be Measured Before Activation

- Choice integrity (4 choices, 1 correct) for every selected item.
- Rule 1a + 1b collision clean for every selected item.
- No duplicate lemmas against active verb bank.
- Staging import row counts correct.

## What Is Forbidden Until Real-Signal Gates Are Met

- Tranche2 activation.
- Selector changes.
- Deactivation of tranche1 items (except for documented correctness failures).
- Any claim about verb bank health based on session heuristics alone.
