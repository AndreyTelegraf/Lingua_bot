Task: prepare import-ready staging artifacts from approved candidates.

Repository root: /home/andrey/Projects/lingua_bot_v2
Environment: staging only
Mode: import preparation only

Inputs:
- approved.csv
- existing import tooling and diagnostics scripts

Rules:
- do not apply changes
- do not write to DB
- prepare only deterministic artifacts for a human-reviewed staging apply step

Outputs:
- import_ready.csv
- apply_staging_microbatch.sh
- post_apply_checks.sh
- import_prep_summary.json

Checks to include:
- DB backup creation
- dry-run validation
- rebuild choice packs if needed
- contract smoke
- selector QA
- service restart only after checks pass

End with:
- exact file paths
- exact counts
- exact command to run locally
