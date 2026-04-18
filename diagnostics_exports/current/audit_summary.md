# Vocab Bank Diagnostic Audit
**Date:** 2026-04-17  
**DB:** data/lingua_staging.db (staging, read-only)  
**Mode:** read-only audit

---

## Bank Size

| Status | Count |
|---|---|
| Total items | 9,092 |
| Active | 797 |
| Inactive | 8,295 |

---

## Coverage by POS × Bin (active items)

| POS | 1K | 2K | 5K | 10K | 20K | Total |
|---|---|---|---|---|---|---|
| noun | 107 | 124 | 153 | **1** | — | 385 |
| adjective | 32 | 42 | 59 | 47 | 16 | 196 |
| verb | 30 | 33 | 57 | 41 | 15 | 176 |
| adverb | 25 | 4 | 10 | **1** | — | 40 |
| **Total** | 194 | 203 | 279 | 90 | 31 | **797** |

**Critical gaps:** noun/10K = 1 item; adverb/10K = 1 item; adverb/2K = 4 items.

---

## Findings

### 1. Duplicate Lemmas — 4 cases
- `perto` (adverb/1K): items 3383 and 10722 — **exact duplicate, same pos/bin** → deactivate 10722
- `junto` (adjective/1K + adverb/1K): cross-POS duplicate → review test function overlap
- `rosa` (noun/2K + adjective/2K): cross-POS duplicate → review
- `rápido` (adjective/1K + adverb/5K): cross-POS cross-bin → monitor

### 2. Concept Group Misassignments — 3 confirmed
- `trair` (C1 verb, betray) assigned to `food_daily` — wrong group
- `cena` (A2 noun, scene) assigned to `shopping_money` — wrong group
- `feliz` (adjective, happy) assigned to `time_basic` — wrong group

### 3. Selector Repetition Risk — ELEVATED
- All 847 exposure records dated 2026-03-29 (one smoke session)
- `shown_count` ranges from 51–171 across all items
- `answered_count = 0` for all items in `vocab_item_exposure` — tracker appears untracked
- Real usage: 504 answers, 21 attempts, 81 finished attempts — very thin sample
- **Do not base statistical conclusions on current accuracy data**

### 4. Cognate / Internationalism Risk — 13 items
Full suffix set checked: `*ção, *são, *mente, *ismo, *ista, *idade, *logia, *grafia, *ível, *ável, *tico`. Zero matches on first 8 patterns. Matches on `*ível`, `*ável`, `*tico`.

**Confirmed transparent cognates (11):**
- `*ível/*ável`: `impossível` (2K/A2), `possível` (5K/—), `terrível` (5K/B2), `visível` (5K/B2), `invisível` (10K/B2), `aceitável` (10K/C1), `variável` (10K/C1), `vulnerável` (10K/C1)
- `*tico`: `fantástico` (5K/B2), `democrático` (5K/B2), `artístico` (10K/B2)

**Borderline (2):** `sensível` (5K/B2) — EN cognate but gloss diverges; `nível` (1K/A2) — internationalism

Note: `*tico` items were missing from the initial audit due to cascade cancellation. Previous count was 10; corrected count is 13.

### 5. Too-Easy-for-Band — 14 items (low confidence, n=3–4)
- Most are 1K/A1 nouns with 100% accuracy — expected for that band
- Suspicious: `escrever` (5K/B1) at 100% accuracy n=3 — needs more data
- `perto` (adverb/1K/A2) at 100% — also flagged as duplicate lemma
- **Do not act on these until n ≥ 10**

### 6. Distractor Anomalies — 28 items
**Type A — weak Russian distractor `аж` (5 items):**  
Items 3348/3368/3375/3393/3402 (all adverb/1K/A1) share `аж` as a choice — colloquial Russian slang, inappropriate as a distractor.

**Type B — 6-choice format (20+ items, ids 10699–10728):**  
Non-standard choice count (position_index 0–5 instead of 0–3). Selector behavior with 6-choice items is unverified. These are the most recently added items and include the only active noun/10K item (travesseiro, id=10727).

### 7. Missing Metadata
- 94 active items missing `cefr_estimate` (mostly verb/5K, verb/2K, adjective/5K)
- 94 active items missing `concept_group`

### 8. Runtime Flag (no action)
`vocab_item_exposure.answered_count` is not updated when answers are recorded in `vocab_answers`. This is a runtime logic observation — do not fix silently during bank work.

---

## Risk Register

| Priority | Issue | Items Affected | Action |
|---|---|---|---|
| P0 | noun/10K coverage gap | 1 active item | Generate next wave |
| P0 | perto exact duplicate (3383 vs 10722) | 2 | Deactivate 10722 in patch |
| P1 | 6-choice items unverified by selector smoke | ~20 | Selector smoke before use |
| P1 | Transparent cognate ível/ável/tico items | 13 | Hold/reject in next judge pass |
| P2 | concept_group misassignments | 3 | Patch separately |
| P2 | `аж` distractor in 5 adverb items | 5 | Patch separately |
| P3 | 94 items missing cefr_estimate | 94 | Metadata fill wave |
| INFO | answered_count not tracked in exposure | all | Flag to runtime team |

---

## Next Recommended Segment
**noun / 10K / B2** — micro-batch generation  
Target: 40 new items  
Preconditions: validate this audit, resolve perto duplicate, confirm 4-choice format only

---

## Recommended Next Command
```
Submit audit_summary.md + audit_validation_report.md to ChatGPT for review.
Do not proceed to generation until ChatGPT approves.
```
