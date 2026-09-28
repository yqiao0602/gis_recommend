# Legacy GEE Step1-8 pipeline

This bundle preserves the original GEE workflow extraction and Step1-8 production path outside the active QGIS source-grounded mainline.

Runtime implementations live in `src/gis_recommend/legacy/gee_pipeline/`. Thin wrappers remain under `gis_recommend.data` so historical commands and the current Step8 provenance contract keep working.

Retained compatibility command:

```powershell
python -m gis_recommend.data.pipeline_runner
```

Current v2 rebuilds must use `scripts/run_v2_full_pipeline.sh`. The archived `tools/run_full_pipeline.sh` mixes old `outputs/` cleanup with newer defaults and must not be used for current data.

Historical tests are under `legacy/gee_pipeline/tests/` and are excluded from routine pytest collection.
