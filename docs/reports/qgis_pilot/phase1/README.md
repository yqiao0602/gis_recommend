# Phase 1 QGIS Source Inventory

- Facts: 20,428 rows, 20,394 unique descriptions, no blank descriptions.
- Artifact matches: 20,413 rows matched; 15 missing.
- Provenance: 18,526 rows have one extraction group; 1,887 rows have two or three groups and require path/hash resolution.
- Indexed artifacts: 262,110 files, comprising 52,422 each of AST, steps, data, edges, and process-relations files.
- Additional description sources: 2,009 plugin metadata files, 2,054 README files, 851 model/tutorial metadata files, two fine-evaluation CSV files, and 48,011 source scripts that may contain docstrings.
- Source-root metadata was unchanged before and after the scan. All four generated data artifacts were written under `/home/qy/system_redesign/outputs_v2/qgis_pilot/pilot_v1/phase1` and are recorded in `write_ledger.json`.
- The 107 ID mapping contains 107 codes, but none of its 464 `qgis_to_l3` mappings target the 13 added codes. A reviewed 107-specific QGIS crosswalk must be built from ordered evidence.

Large JSONL indexes remain on the server. This directory stores the bounded report and write ledger only.
