# GEE Corpus Authority Manifest Design

## Goal

Build one reproducible, read-only inventory that links the surviving GEE source
scripts under `/home/yll/GEE/Data` to the task metadata under
`/home/yll/GEE/描述性知识抽取汇总`. This inventory replaces the historical
11,397-row subset as the input authority for future complete-DAG recovery.

## Scope

The source scope is limited to the 31 GEE main batches `data10000` through
`data400000`. The early mixed-platform directories (`data0`, `data00`,
`data000`, `data00000`, and `data1`), `*_AST_failed`, QGIS, and ArcGIS
directories are excluded explicitly. `/home/yll` is read-only.

This phase inventories identity and metadata only. It does not run Step1-8,
extract an operator chain, grant training admission, call an LLM, or train a
model.

## Authority Model

Each source path receives a byte-level SHA256 and a stable record key made from
`batch_name + script_filename`. Source instances are grouped by SHA256, while
all paths in every duplicate group remain in the ledger. Canonical selection is
deterministic and prefers a non-mirror batch; `data290000` is recorded as a
known mirror of records already present in `data280000`.

Facts are parsed with Python's CSV parser, not line counts. Their primary
identity is `facts_file + row_number`; `File Name` alone is never authoritative.
The facts file name defines its expected source batch. A fact is joined only
when the expected batch and filename resolve to one source instance. Unique
basename fallback may be reported as a diagnostic suggestion, but it cannot be
promoted to an authoritative join.

## Fail-Closed Statuses

The ledger must preserve, rather than repair, these cases:

- `authoritative_exact_batch_join`
- `source_duplicate_content`
- `known_mirror_instance`
- `facts_conflict`
- `facts_source_missing`
- `source_facts_missing`
- `batch_range_mismatch`
- `invalid_source_filename`

No status in this phase means that a row is a complete or usable workflow.

## Outputs

Large JSONL ledgers and hash indexes are written under
`/home/qy/system_redesign/diagnostics/gee_corpus_authority_20260729/`. The
repository receives only a compact summary/report and its hash ledger. The
summary must expose instance count, unique content count, duplicate groups,
exact facts joins, every fail-closed reason, and per-batch counts.

## Verification

Fixture tests cover mirror deduplication, same-name/different-content sources,
conflicting facts, missing sources, missing facts, malformed names, stable
ordering, and deterministic output hashes. A real server run must be repeated
twice and produce identical summary counts and content hashes. Existing
historical counts are comparison evidence only, not assertions forced onto the
new inventory.

