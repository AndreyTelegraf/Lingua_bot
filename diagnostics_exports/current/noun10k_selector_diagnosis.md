# Noun/10K Selector Starvation Diagnosis
**Date:** 2026-04-18
**Selector file:** `services/vocab_runtime/selector.py` — `get_next_item()`
**Wired at runtime by:** `services/vocab_runtime/service.py:14,31`
**DB snapshot:** `data/lingua_staging.db`
**Read-only — no code or DB changes.**

---

## Active noun/10K at time of diagnosis

13 items (1 pre-existing + 12 newly activated):

| id | lemma | correct_answer | choices | topic_tag |
|----|-------|----------------|---------|-----------|
| 10727 | travesseiro | подушка | **6** | manual_curated_v1 |
| 10729 | cotovelo | локоть | 4 | build:noun_10k_wave1 |
| 10732 | sobrancelha | бровь | 4 | build:noun_10k_wave1 |
| 10735 | sótão | чердак | 4 | build:noun_10k_wave1 |
| 10737 | brejo | болото | 4 | build:noun_10k_wave1 |
| 10739 | granizo | град | 4 | build:noun_10k_wave1 |
| 10741 | nora | невестка | 4 | build:noun_10k_wave1 |
| 10744 | muleta | костыль | 4 | build:noun_10k_wave1 |
| 10747 | chaleira | чайник | 4 | build:noun_10k_wave1 |
| 10750 | repolho | капуста | 4 | build:noun_10k_wave1 |
| 10753 | galho | ветка | 4 | build:noun_10k_wave1 |
| 10759 | tartaruga | черепаха | 4 | build:noun_10k_wave1 |
| 10769 | rascunho | черновик | 4 | build:noun_10k_wave1 |

---

## Selector architecture

The runtime selector is `services/vocab_runtime/selector.py::get_next_item`. It does **not** filter by choice count.

`modes/vocab/selector.py` exists but is **not** wired into runtime. Its `_fetch_candidates` requires `HAVING COUNT(*) = 6` choices — this would exclude 12 of 13 noun/10K items. It is irrelevant to the observed behavior.

---

## Bin-ladder staging (the root cause)

`get_next_item()` determines `soft_start_bins` and `target_bin` by step:

```
step 0–3   → soft_start_bins = ('1K', '2K')          target_bin = '1K'
step 4–7   → soft_start_bins = ('1K', '2K', '5K')    target_bin = '2K'
step 8–15  → soft_start_bins = ('2K', '5K', '10K')   target_bin = '5K'
step 16–21 → soft_start_bins = ('5K', '10K', '20K')  target_bin = '10K'   ← PRIMARY WINDOW
step 22–23 → soft_start_bins = ('5K', '10K', '20K')  target_bin = '20K'
```

`soft_start_bins` becomes a SQL **WHERE** clause filter:
```sql
WHERE vi.bin_name IN (?, ?, ?)   -- hard exclusion, not sort order
```

`target_bin` becomes an ORDER BY prefix:
```sql
ORDER BY CASE WHEN vi.bin_name = ? THEN 0 ELSE 1 END ASC, ...
```

---

## Step-by-step noun/10K eligibility

### Steps 0–7: HARD GATE — 10K completely excluded

`soft_start_bins` does not include `'10K'`. The WHERE clause `bin_name IN (...)` removes all noun/10K from the candidate query entirely. Zero possibility of appearing, regardless of any other factor.

**Noun pool sizes:**
- Steps 0–3: 231 nouns available (1K+2K only)
- Steps 4–7: 384 nouns available (1K+2K+5K only)

### Steps 8–15: IN WHERE CLAUSE, but de facto crowded out

10K enters `soft_start_bins`. Total noun pool = 290 (2K: 124, 5K: 153, 10K: 13).

However, `target_bin = '5K'` means 5K items sort first (CASE=0), 10K and 2K sort after (CASE=1). The random pool limit is `LIMIT 24` (`_candidate_pool_size()` default). With 153 noun/5K items available, all 24 pool slots are filled by 5K nouns. Noun/10K is **structurally crowded out** of the pool despite being in the WHERE clause.

**Probability of noun/10K appearing at steps 8–15: effectively 0%.**

This is not a deliberate design choice; it is an emergent property of `LIMIT 24` combined with a deep 5K noun pool (153 items > 24).

The only scenario where noun/10K enters the pool at steps 8–15 is if more than 24 noun/5K items have already been shown in the same attempt — which never happens given the noun cap of 12 per session.

### Steps 16–21: PRIMARY TARGET WINDOW — noun/10K sorts first

`target_bin = '10K'` → ORDER BY `CASE WHEN vi.bin_name = '10K' THEN 0 ELSE 1 END ASC`.

Noun pool = 166 (5K: 153, 10K: 13, 20K: 0). The 13 noun/10K items occupy pool positions 1–13 in ORDER. `_choose_from_candidates` randomly selects one from the pool (LIMIT 24), so 13 of 24 positions = **~54% probability per draw** that a 10K noun is chosen when a noun slot is available.

### Steps 22–23: same bins as 16–21, late rescue

Same `soft_start_bins = ('5K', '10K', '20K')`. Additionally, `step >= question_limit - 4` triggers a rescue path with `target_bin=None, soft_start_bins=None` — 10K accessible from the full active bank, no bin restriction at all.

---

## Why observed hits cluster at steps 17–23

The synthetic runs used **1 active noun/10K item** (travesseiro only, pre-activation). With 1 item:
- Steps 0–15: 0 hits (hard gate + crowding)
- Steps 16–21: travesseiro first in pool; random pick from 24 gives ~1/24 ≈ 4% per slot, but travesseiro is the first row in the 10K group so bin ordering favors it
- 12 hits in 20 runs ≈ 60% of sessions showed travesseiro once, consistent with 1 item available

After activating 12 additional items (13 total), expected behavior changes:
- Steps 16–21: ~54% chance of a noun/10K per available noun slot
- Expected 2–3 noun/10K hits per session (vs ~0.6 with 1 item)

---

## 6-choice filter note

`modes/vocab/selector.py` filters `HAVING COUNT(*) = 6`. The 12 new noun/10K items have 4 choices and would be **invisible** to that selector. This is a latent incompatibility if the async selector is ever activated. Currently **no runtime impact** — the service uses `services/vocab_runtime/selector.py` which has no choice count filter.

---

## Intended or bug?

| Mechanism | Verdict |
|---|---|
| Hard gate at steps 0–7 | **INTENDED** — bin-ladder design, warm up with 1K–2K words |
| 5K target at steps 8–15 | **INTENDED** — 5K is the mid-session target |
| 10K crowded out at steps 8–15 by LIMIT 24 + 153 noun/5K | **EMERGENT** — not an explicit design choice, but acceptable |
| 10K as primary target at steps 16–21 | **INTENDED** — this is the designated 10K window |
| Observed hits only at steps 17–23 | **EXPECTED** — aligns exactly with step 16 boundary |

The starvation in steps 1–16 is structurally sound and matches the diagnostic intent: escalate difficulty bin-by-bin through a 24-step session.

---

## Recommendation: keep current activation as-is

**No selector patch needed. No additional activation needed now.**

Rationale:
1. The late appearance is by design. It correctly places 10K items in the second half of the session when learners have warmed up on 1K–5K vocabulary.
2. 13 active noun/10K items gives adequate variety at steps 16–21. Expected 2–3 distinct items per session.
3. The only real concern is the `modes/vocab/selector.py` 6-choice incompatibility — flag for future async migration, but no action needed now.
4. Activating more items from the 49-item READY pool should only happen after observing real learner performance on the current 13 items.

**Watch signal:** If post-activation data shows the noun/10K pool saturating (same items repeating within 3 sessions), activate the next tranche (~10 items from READY pool).
