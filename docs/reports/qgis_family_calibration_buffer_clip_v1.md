# Buffer -> clip family calibration v1

The second family packet was built from the existing normalized Processing
ledger, without rescanning or modifying source data. It contains 54
occurrences from 36 source SHAs and 19 parent structures. Calibration uses 18
source SHAs and holdout uses 18; SHA overlap is zero and all sources are
verified.

The deterministic structural audit produced 34 passed, 20 dependency-only
deferred, and 0 failed. This lane remains candidate-only; no L3, task, I/O,
dedup, Gold/Silver, training, authority, or evaluation admission was granted.

Server outputs:
`/home/qy/system_redesign/diagnostics/qgis_family_calibration_buffer_clip_v1/`
and
`/home/qy/system_redesign/diagnostics/qgis_family_calibration_audit_buffer_clip_v1/`.
