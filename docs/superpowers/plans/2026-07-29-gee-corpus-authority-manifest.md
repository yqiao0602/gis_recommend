# GEE Corpus Authority Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify the authoritative source/facts inventory for the full surviving GEE main corpus.

**Architecture:** A focused library owns discovery, hashing, exact-batch facts joins, duplicate grouping, and fail-closed statuses. A thin CLI writes atomic JSONL/JSON/Markdown artifacts outside `/home/yll`; repository tests use small temporary fixtures.

**Tech Stack:** Python standard library (`csv`, `hashlib`, `json`, `pathlib`, `tempfile`, `unittest`).

---

### Task 1: Lock Corpus Discovery and Join Semantics

**Files:**
- Create: `src/gis_recommend/data/gee_corpus_authority.py`
- Test: `tests/test_gee_corpus_authority.py`

- [ ] Add fixture tests proving that only configured `dataNNNNN` main batches are discovered and mixed-platform/AST-failed directories are excluded.
- [ ] Add tests proving that `facts_summaryNNNNN.csv` joins only to its expected batch and that basename-only matches remain diagnostic.
- [ ] Add tests for duplicate SHA groups, the `data290000` mirror, conflicting fact rows, missing facts, missing sources, and malformed filenames.
- [ ] Run `python -m unittest tests.test_gee_corpus_authority -v` and confirm the new tests fail because the module does not exist.
- [ ] Implement immutable source/fact record dataclasses, batch discovery, streaming SHA256, structured CSV parsing, exact-batch joins, deterministic canonical selection, and explicit status assignment.
- [ ] Re-run `python -m unittest tests.test_gee_corpus_authority -v` and require all tests to pass.

### Task 2: Add a Read-Only Atomic CLI

**Files:**
- Create: `scripts/build_gee_corpus_authority_manifest.py`
- Modify: `tests/test_gee_corpus_authority.py`

- [ ] Add a CLI fixture test that provides temporary source/facts roots and verifies `source_instances.jsonl`, `canonical_sources.jsonl`, `facts_ledger.jsonl`, `join_ledger.jsonl`, `summary.json`, `report.md`, and `hash_ledger.json`.
- [ ] Verify the CLI test fails before implementation.
- [ ] Implement arguments for source root, facts root, output directory, allowed batches, and known mirror batches; reject an output inside the source root.
- [ ] Write every artifact atomically with stable JSON ordering and include input/output SHA256 values in `hash_ledger.json`.
- [ ] Re-run the focused tests and `python -m compileall -q scripts src tests`.

### Task 3: Run the Full Server Inventory Twice

**Files:**
- Create on server: `/home/qy/system_redesign/diagnostics/gee_corpus_authority_20260729/`
- Create locally: `docs/reports/gee_corpus_authority_2026-07-29.md`

- [ ] Run the CLI read-only against `/home/yll/GEE/Data` and `/home/yll/GEE/描述性知识抽取汇总`, writing only to `/home/qy`.
- [ ] Run it again into a separate replay directory and compare all summary and ledger hashes.
- [ ] Check that all 31 expected main batches are present, `data290000` is represented as a mirror rather than silently deleted, and all join failures have enumerated reasons.
- [ ] Copy only the compact report, summary, and hash evidence into the repository report; do not copy the large ledgers.

### Task 4: Switch the GEE Mainline to the New Authority

**Files:**
- Modify only the GEE section: `task_plan.md`
- Modify GEE status only: `docs/CURRENT_STATE.md`
- Modify GEE status only: `docs/CURRENT_STATE.zh-CN.md`
- Append milestone after successful replay only: `progress.md`
- Update GEE evidence only: `docs/PROJECT_CONTEXT.md`
- Update GEE evidence only: `docs/PROJECT_CONTEXT.zh-CN.md`

- [ ] Record the verified raw-to-authority funnel and mark the 11,397/mean-clip work as calibration-only historical evidence.
- [ ] Set the next gate to complete output-relevant dependency-DAG recovery over a fixed calibration sample drawn from the new canonical source manifest.
- [ ] Verify the documentation does not alter QGIS or evaluation statuses.

