# stable108-only recovery audit v1

## Scope

This audit isolates the two `recover_call_graph` rows unlocked only by the
stable108 Smooth mapping. It reuses the existing local-DAG recovery builder
against read-only `/home/yll` sources. It does not relax a recovery rule or
emit training data.

## Result

- Input recovery rows: 2.
- Source SHA verified: 2/2; failures: 0.
- Recovered multi-step local units: 2.
- Structurally eligible units: 0.
- Training rows emitted: 0.
- Both rows recover `gdal:contour -> native:smoothgeometry` with edge `0 -> 1`.
- Both fail closed on `control_flow:try` and downstream low-level data
  transforms after the Processing chain.

The two files are not independent authorities. `git diff --no-index` reports
7 added lines and 0 removed lines; all seven additions are the QGIS plugin
harvest provenance header. The source bodies are otherwise identical, so the
canonical source-body authority support is 1, far below the required 30.

## Decision

Keep both rows in a structural sidecar as `defer_fail_closed`. Do not generate
task text, run dedup/export gates, or emit train-only rows. The stable108
recovery review is closed; work moves to the seven remaining taxonomy gaps.

## Reproduction

The isolated inputs are in `recovery_delta_manifest_v1.jsonl`. On the server,
the existing `scripts/build_qgis_recovery_local_dag_units.py` was run with
that manifest and `PYTHONPATH=/home/qy/system_redesign/src`; outputs are under
`local_dag/`. Source files under `/home/yll` were read only.
