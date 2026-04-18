# Noun/10K Post-Activation Monitoring Plan
**Date:** 2026-04-18
**Basis:** noun10k_selector_diagnosis.md, vocab_diagnostic_contract.md, vocab_constraint_layer.md
**Mode:** read-only monitoring — no DB writes, no code changes, no activation changes

---

## Active pool state at plan creation

| Metric | Value |
|--------|-------|
| Active noun/10K items | 13 |
| Items with 4 choices (new wave) | 12 |
| Items with 6 choices (legacy) | 1 (travesseiro) |
| READY pool available for next tranche | 36 (from import_ready.csv, after 13 activated) |
| Primary selection window | steps 16–21 (0-indexed) |
| Expected noun/10K items per 24-step session | 2–3 |
| Max noun/10K items per session | ~4 (noun cap=12, ~4 noun slots fall in steps 16–21 on average) |

Item IDs active: 10727, 10729, 10732, 10735, 10737, 10739, 10741, 10744, 10747, 10750, 10753, 10759, 10769

---

## Why these specific signals matter

The vocab bank is a diagnostic measurement instrument, not a content bank. Repeated exposure to the same item contaminates measurement: a learner who saw `cotovelo` in session 3 and answers correctly in session 5 is demonstrating recall, not lexical knowledge. Pool depth directly affects measurement validity.

With 13 items and ~2–3 shown per session, a learner cycles through the full pool in approximately **5–6 sessions**. This is the natural repeat boundary.

---

## Minimum sample size before drawing conclusions

| Threshold | Value | Reason |
|-----------|-------|--------|
| Minimum sessions for pool assessment | 30 complete (24-step) sessions | Gives each item ~5–7 exposures on average (30 × 2.5 / 13) |
| Minimum distinct users | 3 | Single-user data reflects individual ability, not pool health |
| Minimum per-item exposures for correctness signal | 5 answers per item | Below 5, correctness rate is unreliable |
| Preferred sessions before any tranche decision | 50 sessions across ≥3 users | Gives ~10 exposures per item; enough to detect skew |

**Do not evaluate any activation trigger before 30 complete sessions are logged.**

---

## Signal 1 — Items per session (pool reachability)

**What to query:**
```sql
SELECT
  va.attempt_id,
  COUNT(DISTINCT va.item_id) AS noun_10k_shown
FROM vocab_answers va
JOIN vocab_items vi ON vi.id = va.item_id
WHERE vi.pos = 'noun'
  AND vi.bin_name = '10K'
GROUP BY va.attempt_id;
```

**Expected value:** 2–3 per complete session.

**Saturation signal (pool running dry):** mean `noun_10k_shown` < 1.5 over 10 consecutive sessions.
This means cooldown filtering or repeat filtering is eliminating items faster than the pool can rotate. The 24h global cooldown (`last_shown_at`) means that if all 13 items were shown within the last 24 hours across users, the primary path finds nothing and falls back to the fallback (apply_cooldown=False) path. With 13 items and multiple concurrent users, this is theoretically possible.

**Underexposure signal:** mean `noun_10k_shown` < 1.0 across 30 sessions.
Only 1 item per session on average — barely useful for diagnostics at this level.

---

## Signal 2 — Per-item exposure distribution (skew check)

**What to query:**
```sql
SELECT
  vi.id, vi.lemma,
  COALESCE(vie.shown_count, 0) AS shown_count,
  COALESCE(vie.answered_count, 0) AS answered_count
FROM vocab_items vi
LEFT JOIN vocab_item_exposure vie ON vie.item_id = vi.id
WHERE vi.pos = 'noun' AND vi.bin_name = '10K' AND vi.is_active = 1
ORDER BY shown_count DESC;
```

**Expected distribution:** roughly uniform across 13 items after 30+ sessions. Variance acceptable because selection is stochastic within the pool.

**Skew threshold (hard):** `max(shown_count) / median(shown_count) > 3.0`
If the top-shown item has been shown 3× more than the median, the random selection is not distributing fairly. Possible cause: one item's `recent_shown_count` is consistently low (never competing with others), or an item is dominating due to its position in the ordered pool.

**Underexposure (per item):** any single item with `shown_count = 0` after 30 qualifying sessions.
An item that has never appeared despite 30 sessions may be structurally unreachable (ID ordering artifact, or bin_exposure_avg anomaly).

---

## Signal 3 — Repeat rate (measurement contamination risk)

The selector has no per-user item memory beyond the global 24h cooldown. A user who completed a session yesterday is not protected from seeing the same noun/10K items today.

**What to query:**
```sql
SELECT
  va1.attempt_id AS session_n,
  va2.attempt_id AS session_n_minus_1,
  vi.lemma,
  vi.id
FROM vocab_answers va1
JOIN vocab_answers va2 ON va1.item_id = va2.item_id
JOIN vocab_items vi ON vi.id = va1.item_id
JOIN vocab_attempts att1 ON att1.id = va1.attempt_id
JOIN vocab_attempts att2 ON att2.id = va2.attempt_id
WHERE vi.pos = 'noun'
  AND vi.bin_name = '10K'
  AND att1.user_id = att2.user_id
  AND att1.id > att2.id
  AND att2.id = (
    SELECT MAX(id) FROM vocab_attempts
    WHERE user_id = att1.user_id AND id < att1.id
  );
```

**Repeat threshold — acceptable:** ≤20% of noun/10K appearances in session N were also in session N-1 for the same user.

**Repeat threshold — concern:** >33% — more than 1 in 3 noun/10K items is a carry-over from the previous session. The pool is too thin relative to session depth.

**Repeat threshold — critical:** >50% — half or more of noun/10K items in a session were already seen last session. Measurement contamination is active.

With 13 items and 2–3 shown per session: if a user sees 3 items in session N, and 2 of those were also in session N-1, the carry-over rate is 67% — critical.

---

## Signal 4 — Correctness rate per item (diagnostic validity)

**What to query:**
```sql
SELECT
  vi.id, vi.lemma, vi.cefr_estimate,
  COUNT(*) AS total_answers,
  SUM(CASE WHEN va.is_correct = 1 THEN 1 ELSE 0 END) AS correct_count,
  ROUND(100.0 * SUM(CASE WHEN va.is_correct = 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_correct
FROM vocab_answers va
JOIN vocab_items vi ON vi.id = va.item_id
WHERE vi.pos = 'noun' AND vi.bin_name = '10K' AND vi.is_active = 1
GROUP BY vi.id, vi.lemma, vi.cefr_estimate
HAVING COUNT(*) >= 5
ORDER BY pct_correct DESC;
```

**Do not interpret correctness rates below 5 answers per item.**

**Calibration bands:**

| pct_correct | Interpretation | Action |
|-------------|---------------|--------|
| > 85% | Possibly too_easy_for_band | Flag for re-evaluation as B1 candidate |
| 40–85% | Healthy B2/C1 range | No action |
| 20–40% | Hard but plausible | Monitor; check distractor quality |
| < 20% | Possibly broken_distractor or ambiguous_gloss | Flag for review; consider deactivation |

These are not hard cutoffs — the diagnostic contract requires human review, not automatic action.

---

## Saturation definition

The pool is **saturated** when the following is true simultaneously:
1. ≥30 complete sessions logged
2. Per-user repeat rate > 33% (Signal 3)
3. Average items per session < 1.5 (Signal 1)
4. Max/median exposure ratio > 3.0 (Signal 2)

Saturation does not require all four simultaneously. Criteria 1 + any one of 2, 3, or 4 meeting threshold constitutes a saturation warning.

---

## Underexposure definition

The pool is **underexposed** (items not being seen enough for reliable measurement) when:
- After ≥30 sessions: any item has `shown_count = 0` (never reached)
- After ≥50 sessions: any item has `shown_count < 3` while the pool mean > 8
- Average noun_10k_shown per session < 1.0 across 30 sessions

---

## Exact activation trigger for ~10 more noun/10K items

Activate the next tranche from `diagnostics_exports/current/import_ready.csv` (READY pool) when **any one** of the following is confirmed, after meeting the minimum sample size requirement (≥30 sessions, ≥3 users):

| Trigger | Condition | Code |
|---------|-----------|------|
| **T1** | Per-user repeat rate > 33% over the last 30 sessions | REPEAT_SATURATION |
| **T2** | Mean noun_10k_items per session < 1.5 over 10 consecutive sessions | POOL_DEPLETION |
| **T3** | Fewer than 10 of 13 items have `shown_count ≥ 3` after 30 sessions | COVERAGE_FAILURE |
| **T4** | Any single item `shown_count ≥ 8` while pool median `shown_count < 3` | EXPOSURE_SKEW |

**Activation is NOT justified if:**
- Fewer than 30 complete sessions in the data
- Real learner data is unavailable (synthetic runs only do not count)
- Any item with ≥5 answers has pct_correct < 20% (unresolved item flaw — fix first)
- A pending constraint audit has not been run (Rule 1 anti-collision must be re-verified against the expanded active bank before staging)

---

## Suggested next tranche selection

If activation is triggered, select ~10 items from the READY pool (`import_ready.csv`, 36 remaining) using these priorities:

1. Prefer CLEAN items over WARN items in `collision_note`
2. Avoid activating both items from any intra-cluster WARN pair in the same tranche (e.g. do not activate both tornozelo and cotovelo simultaneously — cotovelo is already active)
3. Diversify concept_group: at most 2 items from the same concept_group per tranche
4. Re-run Rule 1 anti-collision check against the expanded active bank before applying

---

## Deferred risk: 6-choice incompatibility in `modes/vocab/selector.py`

`modes/vocab/selector.py::_fetch_candidates` contains:
```sql
WITH ready_items AS (
    SELECT vc.item_id FROM vocab_choices vc
    GROUP BY vc.item_id
    HAVING COUNT(*) = 6
)
```

This filter would exclude **12 of 13 active noun/10K items** (all new 4-choice items). Only `travesseiro` (6 choices) would survive.

**Current runtime impact: NONE.** The runtime selector is `services/vocab_runtime/selector.py::get_next_item`, which has no choice count filter. `modes/vocab/selector.py` is not wired to runtime (`service.py:14` imports only from `services/vocab_runtime/selector.py`).

**Trigger for action:** If any migration toward the async selector (`modes/vocab/selector.py` or a variant requiring 6 choices) is planned, this incompatibility must be resolved before activation of further noun/10K items. Options: (a) drop the `HAVING COUNT(*) = 6` requirement from the async selector, or (b) rebuild all new noun/10K items to 6 choices before async migration.

This risk should be recorded and revisited at every future activation decision.

---

## Summary

| Signal | Threshold | Query table |
|--------|-----------|-------------|
| Items per session | < 1.5 mean = depletion | vocab_answers + vocab_items |
| Per-item exposure | max/median > 3.0 = skew | vocab_item_exposure |
| Repeat rate | > 33% = saturation | vocab_answers + vocab_attempts |
| Correctness rate | < 20% = item flaw; > 85% = too easy | vocab_answers |
| Minimum sample | 30 sessions, 3 users, 5 answers/item | vocab_attempts |

**Next command when data is available:**
Run the four Signal queries above against live staging DB. Compare each to threshold. Record counts. If any T1–T4 trigger fires and minimum sample is met, prepare next tranche import following the activation guidance above.
