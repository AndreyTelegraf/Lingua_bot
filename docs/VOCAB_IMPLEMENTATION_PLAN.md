# LinguaBot V2 — Vocabulary Implementation Plan

Architecture layers.

---

# Phase 1 — UX Router

File:
- bot/router_vocab.py

Responsibilities:
- start command
- intro screen
- start button
- question rendering
- result screen

---

# Phase 2 — Selector

File:
- modes/vocab/selector.py

Responsibilities:
- choose item_id
- enforce POS quotas
- enforce CEFR quotas
- enforce bin distribution
- prevent duplicates

---

# Phase 3 — Choices Pipeline

File:
- modes/vocab/choices.py

Responsibilities:
- find distractors
- enforce same POS
- enforce bucket length
- refill strategies
- finalization

---

# Phase 4 — Attempt Logic

File:
- modes/vocab/engine.py

Responsibilities:
- attempt lifecycle
- FSM transitions
- question generation
- answer recording
- abort handling

---

# Phase 5 — Scoring

File:
- modes/vocab/scoring.py

Responsibilities:
- calculate score
- estimate vocab size
- determine CEFR
- produce result DTO

---

# Phase 6 — Telemetry

File:
- modes/vocab/telemetry.py

Responsibilities:
- attempt events
- reject tracking
- selector diagnostics

---

# Phase 7 — Warmup System

Script:
- scripts/warmup_vocab.py

Responsibilities:
- generate synthetic attempts
- measure reject rate
- validate selector stability
