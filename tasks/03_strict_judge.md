Task: strictly judge a generated candidate pool.

Repository root: /home/andrey/Projects/lingua_bot_v2
Environment: staging only
Mode: review only

Inputs:
- gross_pool.csv
- docs/vocab_diagnostic_contract.md
- docs/vocab_rejection_taxonomy.yaml

Rules:
- classify every row as approve / hold / reject
- always provide reason codes
- reject aggressively
- do not write to DB

Outputs:
- approved.csv
- hold.csv
- rejected.csv
- review_summary.json
- adjudication_notes.md

End with:
- exact file paths
- exact counts by status
- recommended next command
