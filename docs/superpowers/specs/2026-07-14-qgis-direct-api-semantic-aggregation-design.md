# QGIS Direct-API Semantic Aggregation Design

## Objective

Convert low-level PyQGIS/C++ API traces into evidence-grounded candidate QGIS Processing operators, then map those operators to the frozen 114-class taxonomy. This phase produces a reviewed pilot corpus, not training data.

## Constraints

- `/home/yll` is read-only; all outputs remain under `/home/qy` and bounded reports are synchronized locally.
- Existing stable-94 and production defaults remain unchanged.
- The provider is OpenAI-compatible at `https://gguuai.com/v1`, model `gpt-5.6-luna`.
- The client reads only `GGUUAI_API_KEY`; secrets, raw provider reasoning, and raw request/response dumps are forbidden in artifacts.
- LLM output is a suggestion. Code evidence plus human adjudication determines accepted labels.

## Pipeline

### 1. Deterministic Compaction

Classify every API call into:

- `processing_operator`: explicit QGIS/GDAL/GRASS/SAGA algorithm IDs;
- `semantic_anchor`: geometry transformation, spatial relation, CRS transform, field calculation, raster math, indexing, or export calls;
- `data_access`: feature iteration, geometry/attribute access, provider reads/writes;
- `infrastructure`: parameter declarations, project/UI registration, logging, feedback, exceptions, and constructors;
- `unknown`: retained for review but never auto-mapped.

Consecutive duplicates are run-length encoded. Infrastructure is summarized by counts. Semantic anchors and data-flow calls retain evidence IDs and source order.

### 2. Ordering Repair

- Valid `statement_index` remains authoritative.
- Missing indices use existing extraction order only as a fallback and are labeled `fallback_extraction_order`.
- No fallback order is reported as deterministic.
- Scope changes, explicit processing calls, and major semantic anchors form segment boundaries.
- Every compacted segment records omitted-call counts and original evidence references.

### 3. Pilot Selection

Build a deterministic 300-record coverage-diagnostic proposal from resolved T2/T3 records. Stratify by extraction source, modality, semantic-anchor family, trace length, and ordering quality. T0 collisions are excluded. This pilot is not an accuracy reference set until humans adjudicate it.

### 4. LLM Aggregation

For each compact segment, provide:

- task name and description as untrusted context;
- explicit Processing operators;
- ordered semantic anchors and data-flow evidence;
- bounded candidate QGIS operators from the catalog;
- frozen 114 mappings and definitions.

Require strict JSON with candidate operator sequence, per-operator evidence IDs, confidence, rejected infrastructure, unsupported fragments, conflict flags, and a short rationale. Low-confidence or unsupported segments return `reject` rather than a guessed operator.

### 5. Review and Admission

Persist JSONL and CSV review artifacts containing deterministic evidence, proposed QGIS operators, mapped L3 codes, reviewer decision, corrections, and failure tags. Never persist hidden reasoning. No row enters SFT before human review and explicit admission policy.

## API Safety

- One-record compatibility smoke precedes batch execution.
- Validate model availability, JSON parsing, timeout, retry, refusal, and forbidden-field rejection.
- Request IDs and response hashes support resumability without storing raw responses.
- The temporary key must be rotated after the pilot.

## Verification

- Unit tests for call classification, run-length compaction, ordering labels, segmentation, candidate selection, strict response validation, and secret/reasoning rejection.
- Integration fixture covering buffer, difference, CRS transform, field calculation, infrastructure-only rejection, and missing statement indices.
- Deterministic 300-record selection with disjoint IDs and recorded seed.
- One live smoke only after offline tests pass.

## Success Criteria

- Review records are compact enough for human inspection and preserve evidence traceability.
- Infrastructure calls cannot become L3 positives by themselves.
- Missing order never becomes falsely deterministic.
- Every proposed operator cites supporting evidence or is rejected.
- Pilot reports separate model proposal quality from adjudicated accuracy.
