# GEE Batch10 v8.9.6 Full Audit

- Scope: the frozen `exhaustive_29` full-coverage audit for the Batch10 v8.9.6
  source-disjoint expansion.
- Result: 28 pass, 1 fail-closed, 0 critical failure; point precision is
  `0.9655172413793104` and the Wilson 95% lower bound is
  `0.8282447812067973`.
- The failed row is `data300000/script_304794.txt` / `output-workflow-1`.
  Its export depends on `annual_col.filter(...).first()` through a loop, but
  the facts and task text contain only the Laos boundary FeatureCollection and
  omit the private imagery dependency.
- Deterministic census: among 55 fact bundles, 37 contain an
  `ee.imagecollection.*` operator chain and exactly one lacks an
  `ee.ImageCollection` dataset fact. That one row is the failed row above.
  The defect is isolated in this batch, so the extractor was not changed and
  the row remains fail-closed.
- The hash-bound evaluator therefore returns
  `failed_rule_repair_required`: one failed row leaves the 29-row Wilson lower
  bound below the required `0.85`. No Batch10 proposal was exported, merged,
  or counted in the existing Batch9 v8.9.5 authority.

Remote evidence root:
`/home/qy/system_redesign/diagnostics/gee_batch10_3000_v8_9_5_20260807/audit_v8_9_6_expression_band_lineage_full/`.
