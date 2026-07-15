# QGIS Core Signature Review v1 to v2 Migration

Date: 2026-07-15

## Reason

Review Batch 03 exposed two scalar control parameters whose identifiers contain
`OUTPUT` but which are not output artifacts:

- `script_56336 / merge / NODATA_OUTPUT` (`Number`)
- `script_56365 / Heatmap / OUTPUT_VALUE` (`Enum`)

Review v1 classified them as outputs. Review v2 derives direction from the QGIS
parameter class (`Destination`, `Sink`, or `Output`) rather than an identifier
substring, so both are correctly inputs.

## Compatibility Check

Structured comparison of all 121 review rows found:

- Missing or added record/class keys: 0
- Changed trace hashes: 0
- Changed exact candidate sets: 0
- Changed ranked candidate sets: 0
- Changed auto proposals: 0
- Changed resolution statuses: 0
- Changed parameter schemas: exactly 2 rows listed above

The 20 user-confirmed Batch 01-02 decisions were migrated without changing any
accepted operator. Each v2 decision retains `migrated_from_review_sha256` and a
machine-readable migration basis.

## Authority

- Review v1 is immutable historical evidence.
- Review v2 is the active adjudication authority.
- v2 review SHA256:
  `d5eee5da32c092c594a63feea4a3cc7cd2b9708dd9ceaa0418f6a1960a57e6f4`.
- v2 full server record SHA256:
  `0f9fa5a8426b5f95e0544e0010e5d0c024adbd9b70cc99aabff201107bec5aed`.
- Migrated decisions validated: 20.
- Remaining review rows: 101.
- Training rows emitted: 0.
