# Family semantic calibration — clip → multipart-to-singleparts

The deterministic audit replayed all seven source-backed packet rows directly
on the server. It verified raw source SHA, AST literal operator IDs and order,
parameter evidence, and the inter-call result dependency (including the local
`clipped['OUTPUT']` alias). Results: 7/7 passed, 0 failed, 0 deferred; 7/7
source SHAs verified; calibration/holdout SHA overlap 0; and seven distinct
normalized AST templates.

This validates the bounded recovery rule only. Task fidelity, official
provider/I/O contracts, current L3 authority compatibility, cross-pool dedup,
and Gold/Silver admission remain closed. The audit emitted zero training rows.

Server output:
`/home/qy/system_redesign/diagnostics/qgis_asset_family_semantic_audit_clip_multipart_v1/`
