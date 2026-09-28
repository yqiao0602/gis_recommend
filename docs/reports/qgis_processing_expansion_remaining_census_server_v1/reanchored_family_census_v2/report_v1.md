# Remaining Processing Reanchored Family Census

Date: 2026-08-07

## Scope

This report covers the Processing blocker authorities outside the first
319-source verified expansion subset. It is a discovery and calibration gate,
not a training export.

## Verified Inputs

- Selected remaining sources: 343.
- Server SHA verified: 323; missing source files: 20, all fail-closed.
- Exact provider proof: 93 `qgis:<slug>` to `native:<same slug>` migrations;
  all other provider or span differences remained rejected.
- Input lanes after verification: 67 `recover_call_graph`, 26
  `split_subworkflow`, and 230 `defer_operator_resolution`.

## Boundary Census

- Recovery replay produced 6 structural-eligible local units; 5 failed the
  deterministic description-fidelity gate.
- Split replay produced 94 local units; none passed the strict multi-step
  boundary plus description gate.
- The one strict remaining unit has one normalized-source-body authority. Its
  local signature is `native:mergevectorlayers -> native:extractbyattribute`.
  It cannot form a source-disjoint calibration/holdout pair, much less meet
  the support-30 family gate.

## Operator-Resolution Census

The 230 operator-resolution records contain 222 normalized-source-body
authorities and 124 exact canonical operator-sequence clusters. The largest
clusters are `native:mergevectorlayers` (11), `native:fieldcalculator` (10),
`gdal:rasterize` (7), and `native:reclassifybytable -> gdal:translate x3` (7).
Every cluster is marked `unproven_operator_resolution_pending`: it has neither
a recovered task boundary nor dynamic/custom operator proof. Therefore no
operator-only cluster is calibration-eligible regardless of raw support.

## Decision

No strict family reaches 30 independent normalized-source-body authorities.
The calibration packet is intentionally empty. No L3 mapping, task description,
train-only row, validation/test row, or production merge is granted.

The reusable command is:

```text
python scripts/census_qgis_processing_reanchored_families.py \
  --source-manifest <provider_verified_sources.jsonl> \
  --recovery-units <recovery_units.jsonl> \
  --split-units <split_units.jsonl> \
  --output-dir <report_dir> \
  --minimum-authority-support 30
```

It only writes a source-disjoint calibration/holdout packet for a strict,
canonical, boundary-complete family at or above the configured independent-body
support threshold.
