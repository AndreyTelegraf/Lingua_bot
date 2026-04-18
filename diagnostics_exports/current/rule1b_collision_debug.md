# Rule 1b Collision Debug Report
**Date:** 2026-04-18
**Script:** `diagnostics_exports/current/apply_staging_microbatch.sh`
**Query:** COLLISION2 (Rule 1b preflight)

---

## Verdict: FALSE POSITIVE — OVERBROAD PREFLIGHT QUERY

Both violations are caused by the preflight distractor list including values from **blocked items** (not included in the INSERT). No READY item uses either value as a distractor.

---

## Exact Violations Found

| # | Active item | id | correct_answer | triggered by | source candidate | source status |
|---|---|---|---|---|---|---|
| 1 | `caixa` | 325 | `ящик` | `ящик` in distractor list | G011 (`prateleira`), G012 (`cabide`) | BLOCKED_COLLISION |
| 2 | `travesseiro` | 10727 | `подушка` | `подушка` in distractor list | G009 (`colchão`) | BLOCKED_COLLISION |

---

## Root Cause

The COLLISION2 preflight query was built from the full distractor pool of all 53 approved items, including the 4 that were **explicitly blocked** before the INSERT was written:

- `подушка` — distractor in G009 (`colchão`), which is `BLOCKED_COLLISION`
- `ящик` — distractor in G011 (`prateleira`) and G012 (`cabide`), both `BLOCKED_COLLISION`

The INSERT statements for these items were intentionally omitted from `apply_staging_microbatch.sh`. Their distractors should not appear in the preflight check.

---

## Verification: READY pool is clean

Neither `подушка` nor `ящик` appears as a distractor in any of the 49 READY items:

```
подушка — only in G009 (BLOCKED). Not in any READY item's distractors.
ящик    — only in G011 (BLOCKED) and G012 (BLOCKED). Not in any READY item's distractors.
```

The 49 READY items have zero Rule 1b violations.

---

## Fix Required

In `apply_staging_microbatch.sh`, remove `'подушка'` and `'ящик'` from the COLLISION2 preflight IN-list. These values belong to blocked items and were erroneously included.

Corrected IN-list for COLLISION2 (values present in READY items' distractors only):

```
'колено','лодыжка','локоть','ступня','подбородок','висок','лоб',
'ресница','зрачок','веко','борода','брови','бакенбарды',
'одеяло','полотенце',
'крыша','подвал','подъезд','чердак','чулан',
'поляна','склон','чаща','вершина','ущелье',
'иней','гроза','ливень','туман',
'зять','тёща','свекровь','невестка','тесть',
'шрам','синяк','ожог','трость','носилки','шина',
'нить','шило','булавка','воронка','ковш','ведро',
'кастрюля','сковорода','кувшин','чашка','кружка','поднос',
'морковь','лук','репа','пшеница','ячмень','овёс','рожь',
'кора','корень','лист','папоротник','гриб','лишайник','трава',
'ворон','ястреб','цапля','сова','коршун',
'ящерица','улитка','жаба','черепаха','змея',
'бобёр','белка','ёж','рысь','выдра','барсук','лиса','куница','олень',
'краб','лосось','мидия','креветка','угорь',
'рукопись','конспект','чистовик',
'осада','облава','сражение',
'совет','устав','съезд',
'расход','счёт','инвестиция',
'обвиняемый','прокурор','присяжный',
'официант','пекарь','кассир',
'балка','доска','кирпич',
'потери','трата','убыток',
'загон','луг','пашня'
```

Removed: `'матрас'`, `'простыня'`, `'подушка'`, `'ящик'`, `'вешалка'`, `'крючок'`, `'полка'`

Note: `'матрас'`, `'простыня'` are distractors in G008 (BLOCKED). `'вешалка'`, `'крючок'`, `'полка'` also come from G011/G012 (BLOCKED). All seven were removed.

---

## After Fix

COLLISION2 count against corrected list: **0 violations**.
The script will proceed past the Rule 1b preflight check and apply the 49 READY items.

---

## Additional Context (from earlier Rule 1a check)

`ящик` also appears as a distractor (not correct_answer) in two other active items:
- `rainha` (id=330): `ящик` is a distractor — no conflict (Rule 1b is about active *correct_answers*, not active distractors)
- `gás` (id=475): `ящик` is a distractor — same, no conflict

These are irrelevant to Rule 1b.
