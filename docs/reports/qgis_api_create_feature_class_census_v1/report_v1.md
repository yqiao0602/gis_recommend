# QGIS API Create Feature Class Census v1

- Input replay rows: 102
- Broad macro contract: 84
- Spatial-semantics-clean rows before CRS transform exclusion: 72
- Strict review eligible: 67
- Calibration / holdout: 20 / 20
- Source SHA overlap: 0
- Normalized body overlap: 0
- Proposed L3: `L3_01_01_01 Create Feature Class`
- Training admission: not granted

The former 72-row count is an intermediate spatial-semantics-clean count. Rows containing an explicit `QgsCoordinateTransform` plus `transform()` remain deferred so that reprojection tasks are not truncated into Create Feature Class samples.
