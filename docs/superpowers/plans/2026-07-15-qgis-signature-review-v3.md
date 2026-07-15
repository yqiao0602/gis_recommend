# QGIS Signature Review v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three source-confirmed GDAL candidates through a deterministic review-authority migration without changing the other 118 rows.

**Architecture:** A reviewed JSON manifest is the only new authority input. A focused migration script validates immutable source hashes, updates three bounded rows, migrates existing decisions to the new review hash with provenance, and emits reproducible reports and a ledger.

**Tech Stack:** Python standard library, CSV/JSONL, SHA256, `unittest`.

---

### Task 1: Lock Migration Invariants

**Files:**
- Create: `tests/test_qgis_core_signature_review_v3_migration.py`

- [ ] Write a test that builds a two-row fixture, migrates one allowlisted row,
  and asserts that only the five candidate/proposal fields change.
- [ ] Write tests that reject stale review/decision hashes, unknown keys, trace
  mismatches, duplicate additions, and candidates already present in v2.
- [ ] Write a test that validates migrated decisions against the new review and
  asserts no new human decision is created.
- [ ] Run `python -m unittest tests.test_qgis_core_signature_review_v3_migration`
  and confirm failure because the migration module does not exist.

### Task 2: Implement the Deterministic Migrator

**Files:**
- Create: `scripts/migrate_qgis_core_signature_review_v3.py`

- [ ] Implement CSV/JSONL loaders, SHA256 validation, manifest validation, and
  exact candidate insertion using sorted JSON serialization.
- [ ] Preserve row ordering and all non-authorized fields byte-for-byte at the
  parsed field level.
- [ ] Migrate each existing decision to the new review hash and append an
  `authority_migration_history` entry containing the immediate v2 hash and
  migration basis.
- [ ] Emit `signature_review.csv`, `adjudication_decisions.jsonl`,
  `migration_report.json`, `migration_from_v2.md`, and `hash_ledger.json`.
- [ ] Run the new test module and confirm all tests pass.

### Task 3: Add the Audited Three-Row Manifest

**Files:**
- Create: `configs/qgis_pilot/qgis_core_signature_v3_candidate_additions.json`

- [ ] Record the v2 review and decision SHA256 values.
- [ ] Add exact source evidence and bounded candidates for
  `gdal:createcog`, `gdal:dataset_identify`, and `gdal:ogrinfojson`.
- [ ] Run the migrator twice into separate temporary directories and compare all
  emitted artifact hashes for determinism.

### Task 4: Generate and Validate Review v3

**Files:**
- Create: `docs/reports/qgis_pilot/phase3_core_signature_review_110_v3/*`
- Modify: `task_plan.md`
- Modify: `progress.md`
- Modify: `docs/PROJECT_CONTEXT.md`
- Modify: `docs/PROJECT_CONTEXT.zh-CN.md`

- [ ] Generate the bounded v3 package from the committed v2 authority.
- [ ] Run the existing adjudication validator and confirm 118 decisions,
  90 accepted, 28 rejected, 3 remaining, and zero training rows.
- [ ] Run a structured row diff and confirm exactly the three allowlisted rows
  changed only in the five authorized fields.
- [ ] Update durable context with hashes, decisions, and remaining gates.

### Task 5: Synchronize and Verify

- [ ] Copy the v3 bounded package and migration script to `/home/qy` only.
- [ ] Run local QGIS discovery and local/server signature migration tests.
- [ ] Run the server validator and compare local/server artifact SHA256 values.
- [ ] Commit only the migration implementation, tests, manifest, bounded v3
  artifacts, and durable context updates using the Lore commit protocol.
