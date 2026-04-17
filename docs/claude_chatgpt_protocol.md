# LinguaBot Claude–ChatGPT Protocol

## Roles

### Claude Code
Executor only.
Responsible for:
- read-only audits
- candidate generation
- strict judging
- import/patch preparation

Claude Code must not be treated as final authority.

### ChatGPT
Validator and architect.
Responsible for:
- checking whether Claude output is trustworthy
- deciding whether to proceed
- correcting task structure
- preventing stale-data or hallucination-driven decisions

## Core rules
- Never trust Claude output without validation.
- Always validate audit output before generation.
- Never run the full pipeline in one Claude session.
- Prefer micro-batches over mass generation.
- Prefer reject over weak approval.
- Do not generate candidates without a validated audit.
- Do not use stale data when fresher trustworthy data exists.
- Use structured outputs (CSV / JSON / MD), not essays.
- Keep prompts short and outputs compact to reduce token burn.

## Canonical workflow
1. Claude Code runs vocab-auditor
2. Claude Code runs vocab-audit-validator
3. ChatGPT reviews audit summary + validation summary
4. Claude Code runs vocab-generator for exactly one approved segment
5. Claude Code runs vocab-judge
6. ChatGPT reviews approved set and risks
7. Claude Code runs vocab-patch-preparer
8. Human runs staging apply and smoke
9. Claude Code or ChatGPT reviews post-wave evidence

## Stop conditions
Stop immediately if:
- audit validator returns FAIL
- freshness is unclear
- more than one segment is recommended
- outputs are vague or unquantified
- Claude proposes DB writes during audit/generation/judge stages
- Claude relies on stale snapshots for final recommendations

## Token-efficiency rules
- Use Sonnet or equivalent by default
- Use larger model only for escalations
- Split work into short sessions
- Keep each task narrow
- Prefer machine-readable artifacts over prose
- Do not ask Claude for long explanations unless necessary

## Decision rule
Claude does.
ChatGPT decides whether Claude should be trusted.
Human moves the pipeline forward.
