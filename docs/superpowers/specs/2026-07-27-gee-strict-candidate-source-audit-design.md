# GEE Strict Candidate Source Audit Design

## Goal

Measure the residual false-negative risk of the 3,106-row GEE strict candidate
bucket with a reproducible, source-backed sample. This phase calibrates the
surface gate; it does not edit individual training rows or grant admission.

## Sample Design

Select 60 unique rows deterministically from
`strict_candidate_v1/gee_strict_candidate_v1_train3106.json`.

- Cover every task type present in the candidate pool before allocating
  remaining slots.
- Fill remaining slots with a deterministic diversity score over chain-length
  band, primary operator family, source directory group, and exact-chain
  frequency class.
- Preserve each selected row's frozen operator sequence, L3 sequence,
  task text, source path, and source SHA256.
- Record the selection algorithm, seed, coverage counts, and retrieval manifest.

Sixty rows are used because zero observed failures give a one-sided 95%
binomial upper bound of approximately 4.87% for the residual failure rate.
Any observed systematic failure blocks admission and routes to a rule repair.

## Source-Backed Replay

Sources are fetched read-only from their recorded server paths into a temporary
SHA-keyed cache. Every source must match its frozen SHA256. The existing Acorn
parser and current deterministic GEE extractor then rebuild the source-backed
core chain.

For each row, record:

- source and AST verification status;
- frozen and replayed core operator sequences;
- added and removed operators;
- exact/subsequence/changed relationship;
- extractor quality flags and fail-closed reason;
- source-backed call evidence and blank human chain/text/L3 verdict fields.

An exact deterministic replay is evidence, not automatic admission. Missing
source, hash mismatch, AST failure, extractor failure, changed chain, or fatal
quality flags remain fail closed.

## Outputs

Write formal artifacts under
`gee_raster_core_batch_training_package_v1/strict_candidate_v1/source_audit_60_v1/`:

- deterministic sample JSONL/CSV;
- source retrieval manifest;
- source-backed replay JSONL/CSV;
- summary, report, and hash ledger.

Temporary source and AST caches remain outside the formal dataset package.
`train11397_*` and the 3,106-row candidate package are immutable inputs.

## Admission Boundary

- `training_admission=not_granted_source_audit_calibration`
- `validation_eligible=false`
- `test_eligible=false`
- `production_merge=not_granted`
- no LLM call and no training run

After replay, differences are handled by systematic rule clusters. No sampled
row is hand-edited as a production-data exception.

## Verification

- TDD covers deterministic selection, task-type coverage, uniqueness,
  source/hash/AST fail-closed behavior, sequence comparison, and non-admission.
- Formal readback verifies 60 unique samples and unchanged source package hash.
- Existing GEE batch/export/smoke regressions must remain green.

