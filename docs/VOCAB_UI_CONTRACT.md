# LinguaBot V2 — Vocab UI Contract

Status: frozen for implementation  
Mode: vocab

---

# 1. Core UI rule

Vocabulary test in LinguaBot must be shown:

- prompt language: Portuguese
- answer language: Russian
- no English in the user-facing vocab flow

This applies to:

- intro text
- question text
- answer choices
- utility buttons
- result screen for vocab mode

---

# 2. Intro screen

Entry point button:

- 🧠 Vocabulary Test

Intro screen purpose:

- explain what the user will do
- explain rough duration
- explain that this is a diagnostic test

Intro copy does not need to be finalized now, but must obey:

- language must not be English
- should be concise
- should mention that the user will choose the meaning of Portuguese words
- should mention approximate duration
- should mention that the test is diagnostic

Allowed CTA:

- ▶ Начать тест

Forbidden on intro screen:

- English copy
- Level/CIPLE controls
- Stop test button

---

# 3. Question screen

Question message must be in Portuguese.

Canonical format:

- Что значит это слово?
- `<PORTUGUESE WORD>`

or an equivalent frozen Russian wrapper + Portuguese target word.

Important rule:

- the target lexical item is Portuguese
- the six choices are translations/meanings in Russian

No English answer choices are allowed.

---

# 4. Answer options

Each question must show exactly:

- 6 answer options
- all 6 are in Russian
- 1 correct option
- 5 distractors

The answer choices are inline buttons.

Contract:

- exactly 6 regular answer buttons
- no fewer
- no more

---

# 5. Utility buttons

Each question must additionally include:

- ❗️ Не знаю
- ⚠️ Сообщить об ошибке

These are separate controls, not part of the 6 regular answer choices.

Forbidden:

- ⛔ Stop test
- English utility labels

---

# 6. Resulting per-question control count

Per question, UI must expose:

- 6 answer buttons
- 1 dont_know button
- 1 report_error button

Total interactive controls on a question screen:

- 8

---

# 7. Report-error semantics

Button:

- ⚠️ Сообщить об ошибке

Purpose:

- let user report a broken item
- report should not silently disappear
- event must be recorded in diagnostics

Initial implementation may be lightweight:

- log event in event stream
- optionally acknowledge with a short confirmation
- move user forward safely

But the button must exist in the UI contract.

---

# 8. Dont-know semantics

Button:

- ❗️ Не знаю

Purpose:

- explicit unknown answer
- first-class path in runtime
- not a fake wrong answer

This path already exists in runtime and must stay exposed in UI.

---

# 9. No-English rule

In vocab mode, English must not appear in user-facing flow.

Forbidden examples:

- "Vocabulary test"
- "Start test"
- "I don't know"
- "Report error"
- English answer options

Allowed internal-only usage:

- code identifiers
- DTO names
- test names
- docs for development outside user-facing strings

---

# 10. Renderer / payload contract implications

Question payload must support:

- Portuguese prompt / item
- exactly 6 Russian answer choices
- dont_know action
- report_error action

Current 4-choice demo payload is insufficient for final UI contract.

This means:

- renderer must be upgraded to 6-choice contract
- seed/demo data must support 6 choices per item
- UI wiring must wait for renderer contract compliance

---

# 11. Frozen constraints for implementation

Frozen constraints:

- prompt language = Portuguese-facing vocab item flow with Russian wrapper if used
- answers = Russian only
- answer count = 6
- utility buttons = `❗️ Не знаю`, `⚠️ Сообщить об ошибке`
- no stop button
- no English in visible UX

