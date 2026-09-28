# QGIS Processing semantic mapping exclusions v1

Date: 2026-08-01

The literal-alias blocker replay exposed two canonical candidates whose legacy
auto-name mappings are not semantically equivalent to the existing stable110
L3 contracts. Both mappings are now fail-closed:

- `qgis:basicstatisticsforfields` is not `L3_01_08_03 Get Count`.
- `native:ruggednessindex` is not `L3_04_01_01 Slope Gradient`.

This authority removes mappings only. It adds no L3 class or token and grants
no training, validation, test, or production admission. Replays must apply
`authority_v1.json` after the legacy crosswalk.
