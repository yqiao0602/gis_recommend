# Dissolve -> multipart-to-singleparts family calibration audit v2

The frozen 86-occurrence packet was replayed on the server with the bounded
container/loop dataflow auditor; the packet was not regenerated.

| result | v1 | v2 |
|---|---:|---:|
| passed | 70 | 73 |
| deferred dependency-rule gap | 16 | 13 |
| failed | 0 | 0 |

All 86 source SHAs remained verified. Calibration contains 20 source SHAs and
holdout contains 20; their overlap remains zero. Three rows moved from
`deferred_dependency_rule_gap` to `passed` (two calibration and one holdout),
with no structural or semantic failure.

Server artifacts:
`/home/qy/system_redesign/diagnostics/qgis_family_calibration_audit_dissolve_multipart_v2/`

Local copies of `summary_v1.json`, `calibration_audit_v1.jsonl`, and
`hash_ledger_v1.json` are stored beside this report. This is calibration
evidence only: L3 mapping, task fidelity, provider/I/O qualification,
cross-pool four-layer dedup, Gold/Silver admission, training, authority, and
evaluation remain closed. The family is not promoted or batch-expanded until
the remaining 13 rows are resolved by a justified bounded rule or explicitly
documented as a deferred boundary.
