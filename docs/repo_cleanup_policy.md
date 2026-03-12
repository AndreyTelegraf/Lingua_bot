# Repository Operating Rules

## What lives in git
- source code
- migrations
- tests
- config templates
- docs
- deployment / utility scripts

## What does NOT live in git
- sqlite databases
- generated banks
- exports
- backups
- snapshots
- logs
- caches
- runtime artifacts
- heavy raw data

## Runtime storage policy
Recommended server layout:
- /opt/bots/lingua_bot/repo
- /opt/bots/lingua_bot/data
- /opt/bots/lingua_bot/banks
- /opt/bots/lingua_bot/exports
- /opt/bots/lingua_bot/backups
- /opt/bots/lingua_bot/logs

## Rebuild policy
Git stores pipelines and scripts, not generated artifacts.
Any bank/export/snapshot must be reproducible from code or stored outside git.

## Commit policy
Before commit:
- no *.db / *.sqlite / *.jsonl / exports / backups in index
- tests green
- repo status clean after commit
