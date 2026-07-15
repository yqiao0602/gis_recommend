# QGIS Signature Review v3 Design

## Objective

Complete the 121-row Core Processing signature review without weakening the
bounded-candidate validator. Review v3 adds candidates only for the three real
GDAL algorithms whose source identities were confirmed after review v2 was
generated: `createcog`, `dataset_identify`, and `ogrinfojson`.

## Chosen Approach

Migrate the immutable v2 review through a separate audited manifest. The
migration tool validates the v2 review and decision-log SHA256 values, the
record/class/trace keys, the source `name()` evidence, and the absence of the
new operator ID from existing candidates. It then changes only the candidate
and proposal fields of the three allowlisted rows.

Rejected alternatives:

- Relaxing the adjudication validator to accept IDs outside the review package
  would remove the bounded-authority guarantee.
- Editing the shared QGIS catalog and rebuilding all 121 rows would create a
  larger, harder-to-audit difference surface.
- Marking the rows unresolved or non-anchor would contradict inspected source
  code proving that each class is a real Processing algorithm.

## Artifacts

- `configs/qgis_pilot/qgis_core_signature_v3_candidate_additions.json`: audited
  source hashes, three record keys, source names, display names, and candidates.
- `scripts/migrate_qgis_core_signature_review_v3.py`: deterministic migration
  and provenance validation.
- `tests/test_qgis_core_signature_review_v3_migration.py`: stale-hash,
  wrong-key, candidate-bound, row-invariance, decision migration, and
  determinism coverage.
- `docs/reports/qgis_pilot/phase3_core_signature_review_110_v3/`: bounded local
  review, migration report, decision log, summaries, and hash ledger.

## Invariants

- Review row count and ordering remain 121.
- Record/class keys, trace hashes, provider evidence, and parameter schemas do
  not change.
- Exactly three rows change, limited to `exact_candidates_json`,
  `ranked_candidates_json`, `auto_proposed_operator_id`, `resolution_status`,
  and `ambiguity_reason`.
- All 118 v2 decisions migrate to the v3 review hash and retain immediate-source
  provenance. No new human decision is created by migration.
- Training rows remain zero and anchor export remains blocked until the three
  v3 proposals receive explicit human decisions.

## Verification

The migration must pass unit tests, the existing adjudication validator, a
structured v2/v3 row diff, deterministic rebuild comparison, local/server hash
comparison, and the existing QGIS test suite. No LLM call, training run,
production taxonomy change, or write under `/home/yll` is permitted.
