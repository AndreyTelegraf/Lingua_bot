# Adverb 5K Activation — Stage 1: Pre-Activation Safety Audit

**Date:** 2026-04-20
**Anchor commit:** 6be394f
**DB:** data/lingua_staging.db

---

## Target Item List

| item_id | lemma | bin_name | correct_answer | is_active |
|---------|-------|----------|----------------|-----------|
| 3958 | frequentemente | 5K | часто | 0 |
| 3960 | geralmente | 5K | обычно | 0 |
| 10017 | novamente | 5K | снова | 0 |
| 3963 | principalmente | 5K | главным образом | 0 |
| 10019 | exatamente | 5K | точно | 0 |
| 3970 | facilmente | 5K | легко | 0 |

All 6 IDs exactly match manifest. All is_active=0 confirmed live.

---

## Pre-flight Checks (all 6 items)

| Check | Result |
|-------|--------|
| Item exists in DB | ✓ PASS (all 6) |
| is_active=0 | ✓ PASS (all 6) |
| pos=adverb | ✓ PASS (all 6) |
| bin_name=5K | ✓ PASS (all 6) |
| correct_answer matches manifest | ✓ PASS (all 6) |
| Exactly 4 choices | ✓ PASS (all 6) |
| Exactly 1 correct | ✓ PASS (all 6) |
| Rule 1a | ✓ PASS (all 6) |
| Rule 1b | ✓ PASS (all 6) |
| Group atomic consistency | ✓ PASS (all 6) |
| Duplicate lemma vs active bank | ✓ PASS (all 6) |

---

## Baseline Active Counts

| POS | Active count |
|-----|-------------|
| adverb | 40 |
| noun | 397 |
| verb | 185 |

---

## Script Scope Confirmation

- Script: `scripts/adverb_5k_activate_DONOTRUN.sh`
- Only DB mutation: `UPDATE vocab_items SET is_active=1, updated_at=CURRENT_TIMESTAMP WHERE id=<approved_id>`
- Applied only to IDs: 3958, 3960, 10017, 3963, 10019, 3970
- No noun/10K mutations: **absent**
- No verb/10K mutations: **absent**
- No selector mutations: **absent**
- No runtime mutations: **absent**
- Forbidden writes absent: **YES**

---

## Stage 1 Verdict

**PASS — Safe to proceed to backup and activate.**
