# LinguaBot V2 — Vocabulary Test Specification

Version: 1.0
Status: SPEC FREEZE
Mode: VOCAB

---

# 1. Goal

Vocabulary test estimates the user's Portuguese lexical size.

Measures:
- recognition of Portuguese words
- knowledge across frequency bands
- lexical breadth

Outputs:
- estimated vocabulary size
- CEFR band estimate
- routing to Level test

---

# 2. UX Flow

User presses:

🧠 Vocabulary Test

Bot sends introduction screen.

## Introduction Screen

Text:

Vocabulary test

You will see Portuguese words and choose the closest meaning.

- 24 questions
- about 2–3 minutes
- adaptive difficulty

Just pick the closest meaning.

Ready?

Buttons:

- ▶ Start test

---

# 3. Question Screen

Message:

What does this word mean?

<PORTUGUESE WORD>

Inline buttons:

- choice1
- choice2
- choice3
- choice4

Extra button:

- 🤷 I don't know

Rules:
- no correctness feedback
- immediately next question

---

# 4. Question Structure

Each item contains:

| field | description |
|---|---|
| item_id | word id |
| lemma | Portuguese word |
| pos | part of speech |
| freq_rank | frequency rank |
| level | CEFR level |
| choices | list of answer options |
| correct_index | correct answer index |

Example:

- lemma: entretanto
- pos: adverb
- freq_rank: 487
- level: B1

Choices:

1. между тем ✓
2. однако
3. сначала
4. поэтому

---

# 5. Selector Algorithm

Selector chooses the next word.

Constraints:
- frequency distribution
- CEFR distribution
- POS balancing
- no duplicates
- cooldown enforcement

## Frequency Bins

| bin | freq_rank |
|---|---|
| 1K | 1–1000 |
| 2K | 1001–2000 |
| 5K | 2001–5000 |
| 10K | 5001–10000 |
| 20K | 10001–20000 |
| rare | >20000 |

## POS Distribution

| POS | target share |
|---|---|
| noun | 35% |
| verb | 30% |
| adjective | 25% |
| adverb | 10% |

## CEFR quotas

| level | max |
|---|---|
| A1 | 6 |
| A2 | 6 |
| B1 | 6 |
| B2 | 4 |
| C1 | 2 |

---

# 6. Choice Generation

Choices are generated using distractors from vocab_items.

Requirements:
- same POS
- active = 1
- exclude current item
- unique options

## Length Bucket

Choices must fall into the same length bucket as the correct answer.

Example:

- correct: "между тем" length=9
- bucket range: 7–11

Distractors must fall into this range.

## Refill Strategy

If fewer than 4 options exist:

1. same bin + rank ±30%
2. same bin + rank ±80%
3. global + rank ±30%
4. global + rank ±80%
5. global no rank

## Finalization

Function:

`finalize_prod_choices_4()`

Steps:

1. ensure correct present
2. POS sanitize
3. bucket gate
4. refill
5. uniqueness check

---

# 7. Attempt Lifecycle

States:

- START
- QUESTION
- ANSWER
- NEXT
- FINISH

## Attempt creation

Record created in:

`vocab_attempts`

Fields:
- attempt_id
- user_id
- started_at

## Question loop

Repeated 24 times:

selector
→ build choices
→ send question
→ wait answer
→ log result

---

# 8. Reject System

If a question cannot be built:

`reject_reason_code` recorded.

Examples:

| code | meaning |
|---|---|
| pos_leak_production | POS mismatch |
| insufficient_same_pos_choices_prod | distractors unavailable |
| choices_contains_stopword | bad distractor |

Abort rule:

10 consecutive hard rejects → abort attempt.

---

# 9. Result Calculation

After 24 questions:

`score = correct / total`

Vocabulary estimate:

| score | vocab size |
|---|---|
| <20% | 500 |
| 20–40% | 1000 |
| 40–60% | 2000 |
| 60–75% | 4000 |
| 75–90% | 6000 |
| >90% | 8000+ |

## CEFR mapping

| vocab size | CEFR |
|---|---|
| <1000 | A1 |
| 1000–1500 | A2 |
| 2000–3000 | B1 |
| 3000–5000 | B2 |
| >5000 | C1 |

---

# 10. Result Screen

Message:

Your vocabulary size

≈ XXXX Portuguese words

Estimated level:
<CEFR>

Additional text:

You understand most everyday vocabulary.

Next step — check your grammar and reading level.

Buttons:
- 📊 Take full level test
- 🔁 Retake vocabulary test

---

# 11. Persistence

Tables:
- vocab_attempts
- vocab_answers
- vocab_attempt_events

## Events

| event | meaning |
|---|---|
| attempt_started | start |
| question_shown | question delivered |
| answer_selected | user answered |
| item_reject | invalid generated item |
| attempt_aborted | aborted |
| attempt_finished | finished |

---

# 12. Production Warmup

Warmup run:

2000 generated questions

Metrics:
- selector stability
- refill success
- reject rate

---

# 13. Test Length Justification

24 questions balances:
- statistical signal
- Telegram UX speed
- routing accuracy

Expected precision:

±700–900 words
