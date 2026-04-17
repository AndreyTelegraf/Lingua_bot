Task: perform a fresh read-only diagnostic audit of the current vocab bank.

Repository root: /home/andrey/Projects/lingua_bot_v2
Environment: staging only
Mode: read-only

Do the following:
1. Inspect vocab-related schema, scripts, diagnostics outputs, and recent artifacts.
2. Produce:
   - coverage by pos x bin
   - duplicate lemmas
   - duplicate concepts / near-duplicates
   - recent selector repetition risk
   - high-risk cognate / internationalism risk
   - likely too-easy-for-band candidates
   - distractor-quality anomalies
3. Choose exactly one next target segment with the highest ROI.
4. Do not write to DB.
5. Output only machine-readable and reviewable artifacts:
   - audit_summary.md
   - coverage_matrix.csv
   - duplicate_lemma_risk.csv
   - duplicate_concept_risk.csv
   - repeat_risk.csv
   - cognate_risk.csv
   - too_easy_risk.csv
   - distractor_anomalies.csv
   - next_segment_recommendation.json

End with:
- exact file paths
- exact counts
- a recommended next Claude task
