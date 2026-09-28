# QGIS LLM Operator Extraction v1

## Objective

Use TokenRhythm `deepseek-v4-flash-0731` only to identify QGIS Processing operator
calls from source code. Existing deterministic processing remains the authority for
workflow boundaries, L3 mapping, descriptions, deduplication, and training export.

## Contract

```text
source SHA + AST
-> bounded source scope with original lines and required static bindings
-> catalog shortlist (AST facts + lexical retrieval + embedding Top-K)
-> LLM operator candidates with source lines
-> local catalog/span/source verification
-> verified_operator_calls
-> existing unified driver and training gates
```

The model never emits L3 labels, task descriptions, workflow edges, training rows,
or authority updates. Each source may produce zero or more scopes. Every scope and
operator candidate keeps `record_id`, `source_sha256`, scope span, operator ID, and
source-line evidence.

## Candidate Shortlist

The full catalog is not sent to the model. Candidate options are built in fixed order:

1. AST-proven literal IDs and unique prior static string bindings.
2. Lexical provider/slug/function/parameter matches.
3. Local embedding retrieval over the QGIS catalog, default Top-K 16.

Only catalog IDs are eligible. Candidate retrieval is an aid, never a label.

## Model Output

```json
{"operators":[{"catalog_operator_id":"native:buffer","source_lines":[42]}]}
```

Local validation rejects IDs outside the catalog/options and spans outside the submitted
scope. A literal or static alias must also pass independent AST verification. An
unverifiable dynamic candidate remains deferred until source review; it is never silently
promoted.

## 100-Source Pilot

The first mixed pilot contains exactly 100 SHA-verified sources:

- 50 from `processing_source_manifest_v1.jsonl`;
- 50 from `api_source_manifest_v1.jsonl`.

Selection is deterministic, source-SHA unique within and across pools, and staged from
the read-only `/home/yll` tree. The pilot sends bounded scopes, not whole repositories,
and writes only source/scope/candidate ledgers plus hashes. No training rows are emitted.

Pilot review measures:

- request/parse failure rate;
- catalog candidate validity;
- source-line evidence validity;
- operator recall against deterministic literal gold and manually adjudicated dynamic controls;
- unverified candidate count;
- scope-too-large and abstention counts;
- Processing/API result breakdown separately.

## Acceptance Gates

The pilot can feed the existing driver only when every admitted candidate has catalog
membership, source-span evidence, and independent verification. Dynamic candidates without
such evidence remain deferred. A successful pilot changes only operator-resolution input;
it does not change the L3 taxonomy, training schema, or production authority.

## Prohibitions

No whole-file truncation, no guessed operator IDs, no L3 or description generation by the
LLM, no training/checkpoint/validation/test execution, no `/home/yll` mutation, and no
production merge.
