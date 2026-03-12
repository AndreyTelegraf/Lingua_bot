# LinguaBot V2 — Vocab DB Contract

Status: draft frozen for implementation
Mode: vocab

---

# 1. Design principles

Vocab mode must support:

- exactly 24 questions per attempt
- adaptive item selection
- POS balancing
- CEFR quotas
- frequency-bin balancing
- explicit dont_know answers
- reject accounting
- stable result persistence
- routing into Level mode

The DB contract must support production runtime and diagnostics.

---

# 2. Core entities

## vocab_items

Purpose:
- canonical lexical bank for vocab mode

Required fields:
- id
- lemma
- pos
- freq_rank
- level
- bin_name
- question_text
- correct_answer
- active
- topic_tag
- cooldown metadata if needed later

Notes:
- vocab bank is independent from Level/CIPLE banks
- selector reads from this table only

---

## vocab_choices

Purpose:
- prebuilt or cached choices per item when needed
- can coexist with runtime distractor generation

Required fields:
- id
- item_id
- choice_text
- is_correct
- position_index

Notes:
- runtime pipeline may regenerate choices
- table remains useful for smoke/demo/bootstrap

---

## vocab_attempts

Purpose:
- one row per vocab test attempt

Required fields:
- id
- mode_run_id
- user_id
- status
- started_at
- finished_at
- aborted_at

V2-required fields:
- question_limit
- questions_answered
- correct_count
- dont_know_count
- hard_reject_streak
- total_reject_count
- vocab_estimate
- cefr_estimate
- confidence
- completion_reason

Notes:
- exactly one terminal outcome: finished or aborted
- no hanging started attempt without runtime state reconciliation

---

## vocab_answers

Purpose:
- one row per shown item answer

Required fields:
- id
- attempt_id
- item_id
- selected_choice_id
- answer_status
- is_correct

V2-required fields:
- answer_kind (selected / dont_know)
- shown_at
- answered_at
- latency_ms

Notes:
- UNIQUE(attempt_id, item_id)
- dont_know must be first-class, not fake incorrect click

---

## vocab_attempt_events

Purpose:
- detailed event stream for diagnostics and analytics

Required event types:
- attempt_started
- question_shown
- answer_selected
- dont_know_selected
- item_reject
- attempt_aborted
- attempt_finished

Recommended columns:
- event_type
- step_index
- item_id
- reason_code
- payload_json
- created_at

---

## vocab_selector_state

Purpose:
- runtime selector memory for current attempt

Must store:
- shown_item_ids
- quota counters by POS
- quota counters by CEFR
- quota counters by bin
- current_item meta
- hard_reject_streak
- total_reject_count
- maybe cooldown trace

Notes:
- source of truth for vocab selector runtime
- can remain JSON-based initially

---

## vocab_result_snapshots

Purpose:
- intermediate and final result states

Must support:
- per-step snapshots
- final terminal snapshot
- scoring payload
- debug payload

---

# 3. Selector contract mapped to DB

Selector needs these item attributes:

- lemma
- pos
- freq_rank
- level
- bin_name
- active

Selector needs these runtime counters:

- questions_answered
- correct_count
- dont_know_count
- hard_reject_streak
- shown items
- POS quota counters
- CEFR quota counters
- bin counters

---

# 4. Choices pipeline contract mapped to DB

Choices pipeline needs:

- item lemma
- item pos
- item freq_rank
- item bin_name
- correct answer text
- distractor candidate set from vocab_items
- reject reason persistence in vocab_attempt_events

Reject reasons expected:
- pos_leak_production
- insufficient_same_pos_choices_prod
- choices_contains_stopword
- missing_correct_in_final_choices
- duplicate_choices_final
- bucket_mismatch_final

---

# 5. Scoring contract mapped to DB

Attempt must persist:

- correct_count
- total_questions
- score
- vocab_estimate
- cefr_estimate
- confidence
- completion_reason

Also update shared tables:

- mode_results
- user_mode_priors

Expected routing fields:
- vocab_estimate
- last_vocab_band / cefr_estimate
- vocab_confidence
- recommended_level_start_band

---

# 6. Migration plan

## 013_vocab_contract_v2.sql
Add fields required for real 24-question attempt contract.

## 014_vocab_selector_runtime.sql
Add selector-runtime support fields and indexes.

## 015_vocab_rejects_and_result_fields.sql
Add reject accounting and result persistence fields.

All migrations must be additive and safe on current staging DB.
