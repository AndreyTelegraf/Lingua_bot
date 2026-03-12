# LinguaBot V2 — Vocab Selector Policy

Status: frozen for implementation  
Mode: vocab

---

# 1. Goal

Selector must choose the next vocab item for a 24-question attempt while respecting:

- shown-item exclusion
- POS balancing
- CEFR quotas
- frequency-bin logic
- graceful degradation when ideal candidates are not available

Selector must be deterministic enough for testing and observable enough for diagnostics.

---

# 2. Attempt length

Question limit:

- 24 questions exactly

Terminal rule:

- stop when `questions_answered >= question_limit`

Secondary terminal rule:

- stop if selector cannot produce a valid next item under allowed degradation path

Abort rule:

- abort if hard reject streak reaches 10

---

# 3. POS policy

Target shares:

| POS | target share | nominal count at 24 |
|---|---:|---:|
| noun | 35% | 8 |
| verb | 30% | 7 |
| adjective | 25% | 6 |
| adverb | 10% | 3 |

Selector objective:

- prefer the most underfilled POS bucket relative to target
- do not hard-fail if target POS unavailable
- degrade to other POS only through explicit fallback path

Tie-break rule:

- lower observed ratio first:
  - `actual_count / target_count`
- then lower absolute count
- then lower `freq_rank`
- then lower `id`

---

# 4. CEFR quota policy

Maximum quotas across one 24-question attempt:

| level | max |
|---|---:|
| A1 | 6 |
| A2 | 6 |
| B1 | 6 |
| B2 | 4 |
| C1 | 2 |

Rules:

- selector should not pick an item from a CEFR bucket already at max quota
- if all ideal candidates violate quota, degrade to other eligible buckets
- quota is hard unless no full attempt can be constructed otherwise

Recommended initial preference order:

- A1
- A2
- B1
- B2
- C1

This can later become adaptive, but v2 implementation starts quota-first, not CAT-first.

---

# 5. Frequency bin policy

Bins:

| bin | freq_rank |
|---|---|
| 1K | 1–1000 |
| 2K | 1001–2000 |
| 5K | 2001–5000 |
| 10K | 5001–10000 |
| 20K | 10001–20000 |
| rare | >20000 |

Rules:

- selector prefers lower-frequency-rank words first within current policy constraints
- `freq_rank IS NULL` is lowest priority
- `bin_name` is used both for reporting and later balancing
- v2 skeleton does not yet enforce hard bin quotas
- v2 quotas phase introduces soft balancing by bin counters

Initial soft preference:

1. underused bin among eligible candidates
2. lower `freq_rank`
3. lower `id`

---

# 6. Candidate eligibility

An item is eligible only if:

- `is_active = 1`
- not already shown in this attempt
- not excluded by explicit reject/cooldown policy
- has minimal required fields for runtime:
  - `lemma`
  - `question_text`
  - `correct_answer`
  - `pos` preferred
  - `level` preferred
  - `bin_name` preferred
  - `freq_rank` preferred

For v2:
- missing `pos/level/bin_name/freq_rank` does not make item ineligible
- but lowers its preference

---

# 7. Degradation path

Selector tries in this order:

1. ideal candidates:
   - active
   - unseen
   - target POS
   - CEFR under quota
   - preferred bin/freq ordering

2. relaxed POS:
   - active
   - unseen
   - any POS
   - CEFR under quota

3. relaxed CEFR:
   - active
   - unseen
   - any POS
   - any CEFR

4. relaxed metadata:
   - active
   - unseen
   - include NULL metadata items

If still empty:
- selector returns no item
- runtime decides finish or abort based on attempt state and reject logic

---

# 8. Reject / exhaustion policy

Selector itself does not write terminal outcome.

Selector returns either:
- next item
- no item

Runtime then decides:
- finish if `questions_answered >= question_limit`
- finish if no item and attempt already has sufficient answered questions under policy
- abort if no item due to repeated hard rejects / exhausted bank

Expected reject reasons downstream:
- selector_no_candidates_ideal
- selector_no_candidates_pos_relaxed
- selector_no_candidates_cefr_relaxed
- selector_no_candidates_any
- selector_exhausted_bank

---

# 9. State dependencies

Selector reads:

From `vocab_attempts`:
- question_limit
- questions_answered
- correct_count
- dont_know_count
- total_reject_count
- hard_reject_streak

From `vocab_selector_state`:
- shown_item_ids_json
- pos_counters_json
- cefr_counters_json
- bin_counters_json
- current_item_meta_json

From `vocab_items`:
- id
- lemma
- pos
- level
- bin_name
- freq_rank
- is_active

---

# 10. Determinism for tests

For deterministic tests, selector ordering must end with:

- `freq_rank ASC NULLS LAST equivalent`
- `id ASC`

This ensures stable expectations during unit tests.

---

# 11. V2 implementation order

Implementation steps:

1. shown-item exclusion
2. target POS preference
3. CEFR hard-cap filtering
4. soft bin preference
5. degradation path
6. telemetry reason codes

