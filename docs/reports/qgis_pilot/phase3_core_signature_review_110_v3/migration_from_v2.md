# QGIS Core Signature Review v3 Migration

Source review SHA256: `d5eee5da32c092c594a63feea4a3cc7cd2b9708dd9ceaa0418f6a1960a57e6f4`
Target review SHA256: `af39d5cbc43f92e35ca8ecd28605f015f64a68d8236234fa66e2e8857a942f98`

Only the following record/class keys receive new bounded candidates:

- `script_56305 / CreateCloudOptimizedGeoTIFF` -> `gdal:createcog` from source `name()=createcog`.
- `script_56306 / DatasetIdentify` -> `gdal:dataset_identify` from source `name()=dataset_identify`.
- `script_56340 / ogrinfojson` -> `gdal:ogrinfojson` from source `name()=ogrinfojson`.

All other review fields and all existing human decision semantics are preserved.
No candidate is accepted by migration and no training row is emitted.
