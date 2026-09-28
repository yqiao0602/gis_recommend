# QGIS raw-source unclassified detector pilot v1

Date: 2026-09-02

This pilot returned to the original read-only QGIS authorities on `/home/yll`.
It selected a deterministic source-disjoint sample of 100 Processing and 100 API
manifest rows whose existing derived role was `unclassified`. The scanner
re-resolved each source through explicit source roots and recomputed raw-byte
SHA256 before parsing.

## Result

| metric | value |
|---|---:|
| input rows | 200 |
| Processing rows | 100 |
| API rows | 100 |
| source SHA/status failures | 0 |
| Processing operator candidates | 9 |
| Processing workflow candidates (>=2 calls) | 4 |
| API operator/workflow candidates | 0 |
| no known QGIS signature | 187 |
| training rows emitted | 0 |

The observed structural candidate yield is 13/200 (6.5%), concentrated in the
Processing pool at 13/100. This is a detector-yield result only, not a quality
or training-admission estimate. The 187 no-signature rows remain unresolved;
they are not rejected as worthless data.

The first implementation intentionally emits candidate-only structural evidence:
Processing call locations and literal/dynamic argument kind, semantic method
locations, plumbing method locations, source identity, and status. It does not
assign L3, generate task text, modify authority, or write training rows.

## Verification

- Server source roots: `/home/yll/GEE/爬取GIS代码/QGIS_ArcGIS_Textbook_Candidates_Broad`,
  `/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index`,
  `/home/yll/GEE/爬取多源数据源/QGIS_Official_Plugins`,
  `/home/yll/GEE/爬取多源数据源/QGIS_Core_Processing`, and related manifest roots.
- Server output: `/home/qy/system_redesign/diagnostics/qgis_raw_unclassified_pilot_v1/scan_100_v2/`.
- Local focused tests: `tests/test_scan_qgis_raw_unclassified.py` — 3 passed.
- No writes occurred under `/home/yll`, `outputs/`, or `outputs_v2/`.
