# QGIS Core Signature Adjudication Progress

Active review authority: `qgis_core_signature_review_v3`

Authority migration:

- Source review SHA256: `d5eee5da32c092c594a63feea4a3cc7cd2b9708dd9ceaa0418f6a1960a57e6f4`
- Target review SHA256: `af39d5cbc43f92e35ca8ecd28605f015f64a68d8236234fa66e2e8857a942f98`
- Migrated decisions: 118
- Changed review rows: 3
- Authorized changed fields: candidate/proposal fields only

Current status:

- Review rows: 121
- Decisions validated: 121
- Accepted anchor candidates: 93
- Rejected non-anchors: 28
- Remaining: 0
- Training rows emitted: 0
- Anchor export: ready

Final v3 candidates:

| Record | Class | Candidate | Evidence |
| --- | --- | --- | --- |
| script_56305 | CreateCloudOptimizedGeoTIFF | `gdal:createcog` | source `name()=createcog`, GDAL provider, matching multi-raster COG schema |
| script_56306 | DatasetIdentify | `gdal:dataset_identify` | source `name()=dataset_identify`, GDAL provider, folder-recursion/details schema |
| script_56340 | ogrinfojson | `gdal:ogrinfojson` | distinct source class and JSON Processing ID; not merged with `gdal:ogrinfo` |

The user explicitly accepted all three candidates in Batch 13. Review is now
complete and accepted anchors may be exported. Signature acceptance still does
not grant taxonomy or training admission, and no training row has been emitted.
