# QGIS Core Signature Adjudication Progress

Active review authority: `qgis_core_signature_review_v2`

| Batch | Decision | Count | Cumulative accepted |
| --- | --- | ---: | ---: |
| 01 exact GDAL | accept | 10 | 10 |
| 02 exact GDAL | accept | 10 | 20 |
| 03 exact GDAL | accept | 10 | 30 |
| 04 exact GDAL | accept | 10 | 40 |
| 05 exact provider | accept | 10 | 50 |
| 06 exact QGIS | accept | 10 | 60 |
| 07 alias and framework | 5 accept / 4 reject | 9 | 65 |
| 08 GDAL alias and framework | 7 accept / 2 reject | 9 | 72 |
| 09 alias and non-anchor | 8 accept / 2 reject | 10 | 80 |

Current status:

- Review rows: 121
- Decisions validated: 88
- Accepted anchor candidates: 80
- Rejected non-anchors: 8
- Remaining: 33
- Training rows emitted: 0
- Anchor export: blocked until review completion

Important boundaries:

- `contour` and `contour_polygon` are separate operator anchors, not a workflow.
- `gdalinfo` and `ogrinfo` are valid Processing operator anchors; acceptance
  does not automatically grant taxonomy or training admission.
- GDAL provider evidence and parameter schemas disambiguate `rasterize` and
  `translate` from their native QGIS namesakes.
- Plot and other QGIS Processing signatures in Batch 05 remain anchors only;
  acceptance does not automatically grant taxonomy or training admission.
- Histogram, scatterplot, and other reporting signatures in Batch 06 remain
  anchors only and do not automatically enter taxonomy or training.
- `CreateCloudOptimizedGeoTIFF` (`createcog`) and `DatasetIdentify`
  (`dataset_identify`) are real algorithms but remain pending because review v2
  has no correct bounded candidates for them.
- `ogrinfojson` is also a distinct real algorithm and remains pending because
  review v2 lacks `gdal:ogrinfojson` as a bounded candidate.
- Decisions are validated against review SHA256
  `d5eee5da32c092c594a63feea4a3cc7cd2b9708dd9ceaa0418f6a1960a57e6f4`.
