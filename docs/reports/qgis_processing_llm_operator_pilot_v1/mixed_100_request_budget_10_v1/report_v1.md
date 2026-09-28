# Mixed 100-Source LLM Operator Pilot v1

## Scope

This isolated pilot staged 100 SHA-verified, AST-parseable sources from the
read-only server: 50 Processing and 50 low-level PyQGIS API sources. It sent
at most 10 bounded scopes per pool to `deepseek-v4-flash-0731`, for 20 actual
model requests. The remaining scopes are ledgered as deferred by request
budget or size; no source text was truncated.

No training row, L3 assignment, task description, deduplication decision,
checkpoint, validation/test datum, or production authority update was emitted.

## Result

| Pool | Sources | Supported scopes | Sent | Responses | Request failures | Too large | Budget deferred |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Processing | 50 | 69 | 10 | 10 | 0 | 2 | 57 |
| API | 50 | 41 | 10 | 10 | 0 | 1 | 30 |

Processing returned 8 locally-proved catalog IDs across the successful
responses (`native:buffer`, `native:difference`, `native:package`,
`native:reprojectlayer`, `native:saveselectedfeatures`,
`native:selectbylocation`, and `qgis:selectbyattribute`). API returned 19
semantic API IDs across five existing family labels (`feature.setattributes`,
`feature.setgeometry`, `layer.dataprovider`, `layer.getfeatures`, and
`sink.addfeature`).

Every response parsed as JSON, selected only supplied catalog options, and
cited lines inside its source scope. There were no unverified candidate IDs.
The successful-response recall against the local facts in the sent scopes was
100% in both pools. End-to-end recall is deliberately low (Processing 8.5%,
API 26.0%) because 87 of 110 supported scopes were not sent under the fixed
10-per-pool budget, and three oversized scopes were not truncated.

## Interpretation

This validates the operational extraction contract: source scope selection,
catalog restriction, API request, JSON parsing, original-line validation, and
separate Processing/API ledgers all work on real server-sourced code.

It does **not** prove recovery of dynamic IDs or hard-to-extract workflows.
The prompt requires the model to return locally observed facts, so this batch
is a protocol positive control rather than evidence of new extraction yield.
The next scientific gate is a source-disjoint dynamic/partial-evidence
control set where the existing deterministic extractor lacks a final operator
ID; only independently verified new candidates can enter the existing driver.

## Artifacts

- `mixed_sources_100_v1/`: source staging authority and SHA ledger.
- `processing_50_request_budget_10_v2/`: Processing source and scope ledgers.
- `api_50_request_budget_10_v2/`: API source and scope ledgers.
- `api_retrieval_index_v1/`: 24-entry API semantic catalog retrieval index.

## Admission

`training_rows_emitted=0`; training admission and production merge remain not
granted.
