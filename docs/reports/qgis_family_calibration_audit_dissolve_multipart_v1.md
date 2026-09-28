# Dissolve -> multipart-to-singleparts family calibration audit

The 40-source packet was replayed directly against `/home/yll`. All 86
occurrences have verified source SHA, literal operator sequence, matched span,
and parameter evidence; calibration/holdout source overlap is zero.

| result | occurrences |
|---|---:|
| passed current checks | 70 |
| deferred dependency-rule gap | 16 |
| semantic/structural failures | 0 |

The 16 deferred rows use a currently unsupported cross-variable/list-loop
dataflow shape. They are neither admitted nor rejected. No L3, task, I/O,
dedup, Gold/Silver, training, authority, or evaluation admission was performed.

Server output:
`/home/qy/system_redesign/diagnostics/qgis_family_calibration_audit_dissolve_multipart_v1/`
