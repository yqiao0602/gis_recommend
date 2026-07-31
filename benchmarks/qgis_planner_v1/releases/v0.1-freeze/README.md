# QGIS Planner Benchmark v0.1 Freeze

This internal freeze evaluates natural-language planning into parameter-free
QGIS `processes + links`. Development (40), final core (120), and refusal
diagnostic (12) remain separate splits and denominators.

## Prediction Contracts

Graph predictions contain `sample_id`, `processes`, and `links`. Process IDs
are local labels; scoring is invariant to ID renaming and JSON ordering.

Refusal predictions contain `sample_id`, `decision="abstain"`, and one of
`unsupported_capability` or `underspecified_goal`. An empty process graph is
not an abstention.

## Verification And Scoring

```powershell
python scripts/score_qgis_planner_benchmark_v01.py `
  --freeze-manifest benchmarks/qgis_planner_v1/releases/v0.1-freeze/benchmark_manifest.json `
  --graph-predictions path/to/final_predictions.jsonl `
  --refusal-predictions path/to/refusal_predictions.jsonl `
  --output path/to/scores.json
```

The scorer hashes and loads both prediction files before verifying or reading
sealed freeze artifacts. It then verifies the freeze manifest and checksum
ledger, and records both prediction SHA-256 values in the score artifact.
Final prediction files must be locked before sealed gold is opened.
