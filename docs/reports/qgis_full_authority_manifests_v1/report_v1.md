# QGIS full source authority and Processing replay v1

This report is routing-only. It does not grant training admission.

- Processing source authority: **8,466** unique source SHA rows.
- API source authority: **39,386** unique strong-signal source SHA rows.
- Broad low-level API layer: **39,387** rows; the one non-strong-signal row is excluded.
- Processing full source replay: **8,466/8,466** rows.
- Replay actions: direct 100, recovery 222, API sidecar 203, mapping defer 7,913, unparseable exclude 28.
- Training rows emitted: **0**.

The first replay without call-span enrichment is retained only as failed-entry evidence. `processing_full_replay_manifest_v2.jsonl` and `processing_full_replay_summary_v2.json` are the current replay authority.
