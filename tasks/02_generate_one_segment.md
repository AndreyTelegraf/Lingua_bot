Task: generate a gross candidate pool for exactly one target segment.

Repository root: /home/andrey/Projects/lingua_bot_v2
Environment: staging only
Mode: candidate generation only

Inputs:
- docs/vocab_diagnostic_contract.md
- docs/vocab_rejection_taxonomy.yaml
- docs/vocab_segment_plan.yaml
- latest audit outputs

Rules:
- generate candidates for exactly one segment only
- do not write to DB
- do not approve by optimism
- better fewer strong candidates than many weak ones

Output:
- gross_pool.csv
- gross_pool_summary.json

Target size:
- 80 to 150 candidates before review

End with:
- exact file paths
- exact counts
- recommended next Claude task
