# QGIS LLM Mixed Operator Extraction Pilot v1

## Purpose

This is an isolated experiment for the operator-extraction stage only. It sends
bounded source scopes to TokenRhythm `deepseek-v4-flash-0731` and records
catalog-constrained operator candidates with original source-line evidence.
The model does not produce L3 labels, workflow boundaries, descriptions,
training rows, checkpoints, or authority updates.

## Input

The pilot uses the staged, SHA-verified manifest at
`docs/reports/qgis_processing_llm_operator_pilot_v1/mixed_sources_100_v1/`:

- 50 `processing` sources from the Processing authority manifest;
- 50 `api` sources from the API authority manifest;
- 100 unique source SHA256 values; source text is read-only server content;
- `training_rows_emitted` remains `0`.

The unit of accounting is a source and then a bounded function/module scope.
Whole files are never sent. A source with no supported scope is recorded as
`no_supported_scope`, never silently treated as a successful extraction.

## Two extraction contracts

### Processing

The frozen Processing catalog is used. The deterministic gold set consists of
literal or statically proven Processing IDs. Retrieval sends only a shortlist
of catalog IDs to the model. Candidates must be catalog members and cite lines
inside the submitted scope.

### API

Low-level PyQGIS does not have a one-to-one Processing catalog ID. This pilot
therefore uses the versioned semantic API catalog
`docs/plans/qgis_llm_api_operator_catalog_v1.json` with IDs such as
`api:geometry.buffer`, `api:feature.setgeometry`, and
`api:sink.addfeature`. These are extraction labels only; they are not L3
classes. The catalog is derived from the existing deterministic API boundary
families and is deliberately small for the first experiment.

API scopes are functions or top-level statements containing at least one
catalog-supported QGIS API call. GUI, logging, filesystem, and generic Python
calls alone do not create a scope. The local API gold is only a measurable
AST call fact; dynamic or unrecognized calls remain unverified candidates or
deferred.

## Model response and validation

The only accepted response shape is:

```json
{"operators":[{"catalog_operator_id":"api:geometry.buffer","source_lines":[42]}]}
```

Local validation rejects IDs outside the supplied shortlist and spans outside
the original scope. Every ledger row retains source identity, scope span,
catalog options, local facts, proposed IDs, response hash, and status.

## Acceptance gates

The pilot is successful only if both pools have non-zero supported scopes,
request/JSON failures are explicitly counted, all accepted candidates have
catalog membership and valid line evidence, and the result is reproducible
from the staged manifest and hash ledger. Recall is reported separately for
Processing literal gold and API semantic-call gold. No candidate is promoted
to the unified driver without an independent deterministic verification pass.

## Stop conditions

Stop this route after the 100-source pilot if API scopes are zero, request
failures exceed 10%, or valid candidate evidence is absent. If it passes,
run a source-disjoint 25/25 calibration/holdout before considering adapter
integration with the existing deterministic pipeline.

## Prohibitions

Do not send the full catalog, do not truncate source text, do not infer L3 or
descriptions, do not run training, and do not merge isolated results into
Processing/API authority.
