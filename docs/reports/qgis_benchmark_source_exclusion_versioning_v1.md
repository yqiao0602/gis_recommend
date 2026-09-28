# QGIS Planner Benchmark Gate 2 Artifact Versioning Decision

Date: 2026-07-29

Status: selected architecture; local authority and deterministic package built;
release publication pending.

## Decision

Use a GitHub Release asset plus a tracked, hash-pinned manifest for the Gate 2
source exclusion ledger. Do not add the 109 MB raw JSONL to ordinary Git and do
not introduce Git LFS for benchmark v1.

The ledger is audit authority needed for Gate 2 and freeze verification, not a
payload every clone needs. The repository currently has no LFS-tracked files or
verified LFS hosting/quota contract. A release asset keeps normal clones small,
while the tracked manifest detects replacement or corruption through hashes of
both the compressed payload and decoded raw authority.

## Canonical Local Authority

- Path: `benchmarks/qgis_planner_v1/authority/source_exclusion_ledger.jsonl`
- Format: UTF-8 JSONL, LF line endings, terminal LF
- Records: 106,562 (15 artifact inventory + 106,547 exclusions)
- Bytes: 109,617,990
- SHA-256: `b6202e4b0d43123342a701eb5a4bed8b8cb16f64bc9f58e0e545c75553c6fc4c`

The prior 109,724,552-byte hash `0620ae57...` used CRLF because the writer
inherited the host platform newline. It is superseded and must not be published
as benchmark v1 authority.

## Release Contract

The planned tag is `qgis-planner-benchmark-v1.0.0`; the planned asset is
`qgis-planner-benchmark-v1.0.0-source-exclusion-b6202e4b.jsonl.gz`. The tracked
manifest remains `local_packaged_unpublished` until the exact release asset is
uploaded and downloaded back by exact tag/asset URL. Two consecutive local
builds produced identical gzip bytes:

- Bytes: 26,087,577
- SHA-256: `82d1f90a96a2cf3f41127e468a73667f2633f4c47ae6660e1815e7cccbdd1e84`
- Compressor: CPython zlib 1.2.13, level 9, `mtime=0`, empty filename,
  OS header 255

Verification must check the compressed hash and bytes before decompression,
then the decoded raw hash, byte count, record counts, schemas, eight exposure
classes, nine overlap fields, LF-only line endings, and terminal newline. Any
mismatch fails closed. A DOI or read-only object-store mirror is required before
the paper release to reduce GitHub Release availability risk.

## Remaining Publication Work

1. Populate the manifest's producer commit and exact download URL.
2. Create the protected benchmark tag and upload the hash-pinned asset.
3. Run clean-environment download-back verification.
4. Mark the manifest `published_verified`; never replace an existing versioned
   asset in place. Content changes require a new benchmark version.
