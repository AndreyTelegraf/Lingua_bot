# Next POS Track Decision Memo

**Date:** 2026-04-18
**Author:** Claude Code (automated planning artifact)
**Scope:** Verb vs Adverb — which POS to open next after noun/10K wave1
**Input:** `pos_next_track_audit.json`, `pos_audit_inspect.json`

---

## Recommendation

**OPEN VERBS NEXT.**

Confidence: **HIGH.**

---

## Evidence Base

### Current State (from Stage 1 audit)

| Metric | Verbs | Adverbs |
|---|---|---|
| Active total | 176 | 40 |
| All bins OK | YES | NO |
| Thin bins | none | 2K, 10K |
| Empty bins | none | 20K |
| Selector target share | 30% | 10–15% |
| Inactive pool total | 133 | 101 |
| Inactive in needed bins | 17 (10K), 10 (20K) | 5 (10K), 2 (20K) |
| Tools maturity | HIGH | HIGH |
| Fresh generation needed | NO | YES |

---

## Why Verbs Win

### 1. Inactive pool is actionable immediately

Verbs have 133 inactive items including 17 in 10K and 10 in 20K — the two bins where expansion has the most diagnostic value.
The `verb_gloss_rules.py` + `run_verb_ru_gloss_audit.py` pipeline already exists and is tested.
A gloss audit pass followed by a tranche1 prepare cycle is a bounded, known workstream.

This is the same pattern used successfully for noun/10K wave1.
No fresh generation is required before the first tranche.

### 2. Selector impact is highest

The selector targets verbs at **30% share** — 7 of every 24 questions.
Adding activatable verbs directly improves session diversity and measurement coverage across all bin levels.
Adverbs target only 10–15% share — half the per-item impact.

### 3. All verb bins are already healthy

Verbs have 30+ active items in every bin above the selector cap of 10.
This means the current bank is already usable at every bin level.
A tranche1 expansion adds depth to bins that are already functional.
No structural gap needs emergency repair — this is an improvement cycle, not a rescue.

### 4. Proven workflow applies directly

The noun/10K workflow (audit → candidate prep → collision check → tranche1 → monitoring runner) is fresh.
Verbs have dedicated QA tools, gloss audit infrastructure, and test coverage.
The execution risk is low.

---

## Why Adverbs Are Deferred

### 1. Inactive pool does not solve the structural problem

The adverb inactive pool has only 5 items in 10K and 2 in 20K.
Activating the entire inactive pool would leave 10K at 6 items (still THIN, cap=8) and 20K at 2 items (still EMPTY relative to cap).
A single tranche activation cannot fix the structural gap — fresh candidate generation is required.

### 2. Fresh generation adds scope and risk

Generating new adverb candidates at 10K and 20K requires a full Kaikki seed → candidate generation → judge → tranche cycle.
This is a 2–3x larger workstream than activating from an existing pool.
Anti-transparency evaluation at higher frequency bins is more complex (less predictable Russian gloss quality).

### 3. The 1K pool may be contaminated by easy items

Active adverbs at 1K include much/очень, quase/почти, já/уже — items that are near-transparent to any European language learner.
The inactive 1K pool (46 items) needs a transparency audit before activation to avoid inflating easy-question density.
This is a separate quality problem, not a reason to prioritise adverbs.

### 4. Lower selector weight means lower urgency

With only 10–15% target share, each new adverb item has roughly half the session impact of a new verb item.
The 20K adverb gap is real but not session-breaking — the selector falls back to 5K adverbs via soft_start_bins.
Sessions are degraded but not broken. This is a known acceptable state while verbs are expanded.

---

## Deferred Decision: Adverb 10K/20K

The adverb structural problem requires a dedicated planning session scoped specifically to:

- fresh 10K/20K candidate generation (Kaikki or curated source)
- full transparency/anti-cognate review for this bin range
- a standalone monitoring design for adverb-specific signals

This should NOT be bundled with the verb expansion. It is a separate workstream.

**When to schedule:** After verb tranche1 monitoring gate is met and verdict is confirmed.

---

## Explicit Blockers and Assumptions

**Blockers (none that block verbs):**
- None preventing verb tranche1 from starting.

**Assumptions:**
- The 133 inactive verbs were not deactivated due to a systemic policy change (they are candidates for review, not permanently rejected).
- The verb gloss audit will surface a usable subset — exact number unknown until audit runs.
- NULL-bin inactive verbs (23 items) require bin assignment before they can enter the tranche1 pipeline — they are excluded from tranche1 scope by default.

**Risks:**
- If the verb gloss audit reveals that most inactive items are poor quality, tranche1 size will be small. Minimum viable tranche is 5 activatable items.
- The 6 cognate-flagged active verbs (interpretar, distinguir, etc.) are already in the bank and are not a blocker — they are false-positives from the heuristic.

---

## Decision

> **OPEN VERBS NEXT.**
> Scope: audit inactive verb pool → tranche1 prepare (targeting 10K and 20K bins first) → monitoring.
> **DEFER ADVERBS** until adverb 10K/20K generation workstream is scoped separately.
