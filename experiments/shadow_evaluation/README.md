# Archived shadow evaluation tests

This directory preserves the large Phase 1.5–5.5 shadow-evaluation regression suite outside the default test and search surfaces.

The production runtime remains in `gis_recommend.evaluation`; this archive does not retire `gis-evaluate`, `report.py`, `run_contract.py`, or `shadow_phase.py`.

Run the historical suite explicitly from the repository root with the project environment configured:

```powershell
$env:PYTHONPATH = "src;."
python experiments/shadow_evaluation/tests/test_mainline_shadow_phase.py
```

The lightweight default runtime contract is covered by `tests/test_shadow_runtime_smoke.py`.
