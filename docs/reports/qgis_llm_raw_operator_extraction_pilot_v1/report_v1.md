# QGIS Raw-Source Operator Extraction Pilot v1

Date: 2026-08-11

## Scope

This is the first pilot that sends one complete, SHA-verified Python source
file per request. The model receives only a catalog shortlist and must return
catalog operator IDs plus source line evidence. It does not produce L3 labels,
descriptions, training rows, or authority updates.

The frozen packet is source-disjoint from the prior 100-source mixed pilot and
contains 10 Processing plus 10 API sources. Each pool is stratified where
possible into local deterministic facts and no-local-fact sources. Packet SHA:
`b7a7ab1e17945c85260d3cd422efde3045433cdf32903a3603d8979d2b9e75f3`.

## Results

The server runner completed 20 requests (`raw_requests_20_v5`):

| pool | sources | requests without HTTP/parse failure | local gold facts | verified candidates | known-fact recall | precision vs known facts |
|---|---:|---:|---:|---:|---:|---:|
| Processing | 10 | 5 | 27 | 0 | not estimable (all 5 gold requests failed) | not estimable |
| API | 10 | 9 | 8 | 6 | 6/8 = 0.750 | 6/6 = 1.000 |

There were zero `call_site_only` (LLM-only) candidates. The Processing gold
retry (`retry_processing_gold_5_requests_v1`) recovered one locally confirmed
candidate but also returned an incompatible candidate, so the row remained
fail-closed; the other four retries again returned empty/non-JSON content.

All outputs report `training_rows_emitted=0` and
`training_admission=not_granted_raw_operator_pilot`.

## Interpretation

This pilot validates the raw-source request and local call-site/catalog
validation path. It does **not** yet demonstrate recovery of an operator absent
from deterministic extraction: no LLM-only candidate survived validation.
Processing results are currently dominated by service response failures, while
API static calls show a measurable baseline (75% recall, 100% precision on the
small known-fact subset). The route must not be promoted or merged into the
Processing/API mainline based on this pilot.

## Artifacts

- `raw_source_packet_20_v7/raw_source_packet_v1.jsonl`
- `raw_requests_20_v5/raw_operator_ledger_v1.jsonl`
- `retry_processing_gold_5_requests_v1/raw_operator_ledger_v1.jsonl`
- `scripts/build_qgis_llm_raw_operator_packet.py`
- `scripts/run_qgis_llm_raw_operator_extraction_pilot.py`

Ruff and `py_compile` pass locally. Pytest could not be collected in the
current environment because the editable package points at another worktree;
manual assertions for raw validation and packet construction pass.

Decision: keep this route isolated and candidate-only. Before any larger pilot,
fix the service empty-response/rate-limit cause and run a new source-disjoint
holdout with a success-rate gate and an explicit LLM-only recall gate.
