# QGIS Core Signature Adjudication Progress

Active review authority: `qgis_core_signature_review_v2`

| Batch | Decision | Count | Cumulative accepted |
| --- | --- | ---: | ---: |
| 01 exact GDAL | accept | 10 | 10 |
| 02 exact GDAL | accept | 10 | 20 |
| 03 exact GDAL | accept | 10 | 30 |

Current status:

- Review rows: 121
- Decisions validated: 30
- Accepted anchor candidates: 30
- Remaining: 91
- Training rows emitted: 0
- Anchor export: blocked until review completion

Important boundaries:

- `contour` and `contour_polygon` are separate operator anchors, not a workflow.
- `gdalinfo` and `ogrinfo` are valid Processing operator anchors; acceptance
  does not automatically grant taxonomy or training admission.
- Decisions are validated against review SHA256
  `d5eee5da32c092c594a63feea4a3cc7cd2b9708dd9ceaa0418f6a1960a57e6f4`.
