# LinguaBot v2 — Claude Code operating rules

## Project truth
This vocab bank is a diagnostic measurement instrument first, a content bank second.

## Hard constraints
- Work on staging only unless explicitly told otherwise.
- Never write directly to DB unless the task explicitly asks for an import-prep artifact.
- Never activate items automatically.
- Never silently change scoring/selector/runtime logic while doing bank work.
- False positives are worse than false negatives.
- Prefer reject/hold over weak approval.
- Quantify everything.
- Output exact file paths and exact counts.

## Allowed task modes
1. read-only audit
2. candidate generation into CSV/JSONL only
3. strict review / reject / hold
4. import-ready artifact preparation
5. patch scripts for staging only

## Forbidden behavior
- “Looks good overall”
- vague claims
- approving candidates without explicit reason codes
- mixing multiple target segments in one wave
- DB writes during audit mode
- production writes
- hand-wavy band assignment

## Diagnostic principles
Reject or hold anything that is:
- guessable via cognate recognition
- guessable via international root or suffix transparency
- guessable via morphology or part-of-speech giveaway
- solvable through broken or weak distractors
- too easy for its claimed band
- ambiguous in Portuguese prompt or Russian gloss
- duplicate by lemma, concept, or test function
- stylistically inconsistent in distractor set

## Preferred workflow
audit -> choose one target segment -> gross pool -> strict judge -> local validator -> staging microbatch -> rebuild -> contract smoke -> selector QA -> manual smoke

## Output discipline
Always end with:
- files created
- counts by status
- recommended next command
