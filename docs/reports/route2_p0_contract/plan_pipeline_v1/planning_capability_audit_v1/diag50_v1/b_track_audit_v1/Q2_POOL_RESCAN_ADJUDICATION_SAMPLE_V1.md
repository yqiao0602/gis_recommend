# Q2 池级复核判读样本工作表 V1（117 条，seed 20261017）

- **来源**：`Q2_POOL_RESCAN_MECHANICAL_V1.json`（全量机械扫描）按机械类分层抽样，每类≤12。
- **判读口径（owner 裁定）**：差异来源轴四类不互斥（规划结构/参数字面量/实现与脚手架/证据不足）
  + 描述保真度轴独立标记（失实/欠描述/忠实/不可判）。
- 每条给出：双方脚本路径、sha1（是否逐字节同）、diff 行数、机械 flags、保真度提名。
  指令全文见 JSON（`records[].a/.b` 为规范化指令文本）。
- 已知十对的源码级结论可直接沿用（如落入样本）。

## S001 [diff/asset_version_candidate] J=0.8269
- scripts: `script_54184` vs `script_54188` | sha_equal=False | diff_lines=34
- RLE A(6步): `RASTER_LOAD -> COLLECTION_MGMT -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD`
- RLE B(5步): `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=18; families_equal=True; datasets_exact_differ=True; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S002 [diff/asset_version_candidate] J=0.8889
- scripts: `script_28606` vs `script_28603` | sha_equal=False | diff_lines=33
- RLE A(5步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD`
- RLE B(4步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=10; families_equal=True; datasets_exact_differ=True; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S003 [diff/asset_version_candidate] J=0.8
- scripts: `script_54182` vs `script_54187` | sha_equal=False | diff_lines=37
- RLE A(6步): `RASTER_LOAD -> COLLECTION_MGMT -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD`
- RLE B(4步): `RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=4; number_sym_diff_n=20; families_equal=True; datasets_exact_differ=True; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S004 [diff/asset_version_candidate] J=0.8627
- scripts: `script_23493` vs `script_23496` | sha_equal=False | diff_lines=88
- RLE A(19步): `RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> BAND_SELECT -> OTHER_UNMAPPED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER…`
- RLE B(15步): `RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> BAND_SELECT -> OTHER_UNMAPPED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=26; families_equal=True; datasets_exact_differ=True; ui_delta=0; dup_delta=7
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S005 [diff/asset_version_candidate] J=0.7879
- scripts: `script_36129` vs `script_36118` | sha_equal=False | diff_lines=5246
- RLE A(13步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> AGGREGATION -> GEOMETRY_DEFINE -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHME…`
- RLE B(10步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> AGGREGATION -> GEOMETRY_DEFINE -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=3; number_sym_diff_n=0; families_equal=True; datasets_exact_differ=True; ui_delta=1; dup_delta=1
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S006 [diff/asset_version_candidate] J=0.9184
- scripts: `script_16762` vs `script_104683` | sha_equal=False | diff_lines=84
- RLE A(39步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILT…`
- RLE B(35步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILT…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=12; families_equal=True; datasets_exact_differ=True; ui_delta=7; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S007 [diff/asset_version_candidate] J=0.7935
- scripts: `script_213786` vs `script_213790` | sha_equal=False | diff_lines=19
- RLE A(8步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> CLASSIFICATION -> BAND_ARITHMETIC -> AGGREGATION`
- RLE B(10步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> AGGREGATION -> ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> AGGREGATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=3; number_sym_diff_n=3; families_equal=True; datasets_exact_differ=True; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S008 [diff/asset_version_candidate] J=0.8125
- scripts: `script_31850` vs `script_31855` | sha_equal=False | diff_lines=296
- RLE A(3步): `RASTER_LOAD -> CLASSIFICATION -> AGGREGATION`
- RLE B(4步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> CLASSIFICATION -> AGGREGATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=2; number_sym_diff_n=22; families_equal=True; datasets_exact_differ=True; ui_delta=3; dup_delta=40
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S009 [diff/asset_version_candidate] J=0.7903
- scripts: `script_74517` vs `script_74490` | sha_equal=False | diff_lines=78
- RLE A(56步): `ATTRIBUTE_FILTER -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> ATTRIBUTE_FILTER -> RA…`
- RLE B(54步): `ATTRIBUTE_FILTER -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> SPATIAL…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=18; families_equal=True; datasets_exact_differ=True; ui_delta=0; dup_delta=3
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S010 [diff/asset_version_candidate] J=0.75
- scripts: `script_54185` vs `script_54182` | sha_equal=False | diff_lines=54
- RLE A(3步): `RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION`
- RLE B(6步): `RASTER_LOAD -> COLLECTION_MGMT -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=5; number_sym_diff_n=29; families_equal=True; datasets_exact_differ=True; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S011 [diff/asset_version_candidate] J=0.8491
- scripts: `script_54184` vs `script_54187` | sha_equal=False | diff_lines=39
- RLE A(6步): `RASTER_LOAD -> COLLECTION_MGMT -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD`
- RLE B(4步): `RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=4; number_sym_diff_n=22; families_equal=True; datasets_exact_differ=True; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S012 [diff/asset_version_candidate] J=0.7959
- scripts: `script_35908` vs `script_35919` | sha_equal=False | diff_lines=133
- RLE A(20步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> AGGREGATION -> RASTER…`
- RLE B(22步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> AGGREGATION -> RASTER…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=5; number_sym_diff_n=9; families_equal=True; datasets_exact_differ=True; ui_delta=4; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S013 [diff/duplicate_block_candidate] J=0.7612
- scripts: `script_269974` vs `script_269963` | sha_equal=False | diff_lines=549
- RLE A(12步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> BAND_SELECT -> AG…`
- RLE B(13步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> BAND_SELECT -> AG…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=6; number_sym_diff_n=8; families_equal=True; datasets_exact_differ=False; ui_delta=1; dup_delta=86
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S014 [diff/duplicate_block_candidate] J=0.8261
- scripts: `script_10524` vs `script_10526` | sha_equal=False | diff_lines=206
- RLE A(23步): `BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> AGGREG…`
- RLE B(17步): `BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> AGGREG…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=2; number_sym_diff_n=18; families_equal=True; datasets_exact_differ=False; ui_delta=1; dup_delta=9
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S015 [diff/duplicate_block_candidate] J=0.7544
- scripts: `script_1050` vs `script_1051` | sha_equal=False | diff_lines=516
- RLE A(12步): `ATTRIBUTE_FILTER -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> SPATIAL_CLIP -> CLASSIFICATION -> RASTER_LOAD -> SPATIAL_CLIP -> VECTOR_LOAD…`
- RLE B(10步): `ATTRIBUTE_FILTER -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> SPATIAL_CLIP -> CLASSIFICATION -> ATTRIBUTE_FILTER -> AGGREGATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=52; families_equal=False; datasets_exact_differ=True; ui_delta=1; dup_delta=22
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S016 [diff/duplicate_block_candidate] J=0.8478
- scripts: `script_10524` vs `script_10535` | sha_equal=False | diff_lines=96
- RLE A(23步): `BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> AGGREG…`
- RLE B(17步): `BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> AGGREG…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=2; number_sym_diff_n=12; families_equal=True; datasets_exact_differ=False; ui_delta=1; dup_delta=12
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S017 [diff/duplicate_block_candidate] J=0.7931
- scripts: `script_151508` vs `script_151526` | sha_equal=False | diff_lines=735
- RLE A(33步): `VECTOR_LOAD -> AGGREGATION -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> SPATIAL_JOIN -> RASTER_LOAD -> NEIGHBORHOOD -> R…`
- RLE B(34步): `VECTOR_LOAD -> AGGREGATION -> RASTER_LOAD -> ATTRIBUTE_FILTER -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> SPATIAL_JOIN -> RASTER_LOAD …`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=166; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=5
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S018 [diff/duplicate_block_candidate] J=0.7805
- scripts: `script_138658` vs `script_138646` | sha_equal=False | diff_lines=246
- RLE A(19步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> S…`
- RLE B(14步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> SPATIAL_JOIN -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGRE…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=5; number_sym_diff_n=16; families_equal=False; datasets_exact_differ=True; ui_delta=0; dup_delta=7
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S019 [diff/duplicate_block_candidate] J=0.8478
- scripts: `script_111047` vs `script_111048` | sha_equal=False | diff_lines=115
- RLE A(13步): `CLASSIFICATION -> OTHER_UNMAPPED -> RASTER_LOAD -> AGGREGATION -> REGIONAL_STATS -> RASTER_LOAD -> THRESHOLD_LOGIC -> AGGREGATION -> VECTOR_LOAD -> COLLECTION_MGMT -> VECTOR_LOAD -…`
- RLE B(9步): `CLASSIFICATION -> OTHER_UNMAPPED -> RASTER_LOAD -> AGGREGATION -> REGIONAL_STATS -> RASTER_LOAD -> THRESHOLD_LOGIC -> AGGREGATION -> CLASSIFICATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=7; number_sym_diff_n=4; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=12
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S020 [diff/duplicate_block_candidate] J=0.7636
- scripts: `script_66366` vs `script_66381` | sha_equal=False | diff_lines=1996
- RLE A(16步): `RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> RAST…`
- RLE B(22步): `RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_S…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=8; number_sym_diff_n=52; families_equal=False; datasets_exact_differ=True; ui_delta=2; dup_delta=37
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S021 [diff/duplicate_block_candidate] J=0.7778
- scripts: `script_228758` vs `script_277196` | sha_equal=False | diff_lines=784
- RLE A(8步): `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> RASTER_LOAD -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER`
- RLE B(9步): `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> RASTER_LOAD -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=13; families_equal=True; datasets_exact_differ=False; ui_delta=2; dup_delta=16
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S022 [diff/duplicate_block_candidate] J=0.7778
- scripts: `script_118778` vs `script_118777` | sha_equal=False | diff_lines=2160
- RLE A(8步): `RASTER_LOAD -> VECTOR_LOAD -> OTHER_UNMAPPED -> RASTER_LOAD -> ATTRIBUTE_FILTER -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION`
- RLE B(5步): `RASTER_LOAD -> ATTRIBUTE_FILTER -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=2; number_sym_diff_n=9; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=6
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S023 [diff/duplicate_block_candidate] J=0.8557
- scripts: `script_231951` vs `script_231947` | sha_equal=False | diff_lines=1162
- RLE A(19步): `RASTER_LOAD -> BAND_SELECT -> NEIGHBORHOOD -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> TEMPORAL_FILTER -> RA…`
- RLE B(27步): `RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> NEIGHBORHOOD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER ->…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=2; number_sym_diff_n=14; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=5
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S024 [diff/duplicate_block_candidate] J=0.7576
- scripts: `script_269974` vs `script_269968` | sha_equal=False | diff_lines=539
- RLE A(12步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> BAND_SELECT -> AG…`
- RLE B(13步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> BAND_SELECT -> AG…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=6; number_sym_diff_n=10; families_equal=True; datasets_exact_differ=False; ui_delta=1; dup_delta=86
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S025 [diff/reorder_refactor_candidate] J=0.7843
- scripts: `script_103222` vs `script_103223` | sha_equal=False | diff_lines=55
- RLE A(9步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> AGGREGATION`
- RLE B(10步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> CLASSIFICATION -> ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> AGGREGATION`
- 机械 flags: canon_multiset_equal=True; canon_sym_diff_n=0; number_sym_diff_n=4; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S026 [diff/reorder_refactor_candidate] J=0.7759
- scripts: `script_306671` vs `script_205671` | sha_equal=False | diff_lines=66
- RLE A(6步): `GEOMETRY_DEFINE -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY -> AGGREGATION`
- RLE B(6步): `GEOMETRY_DEFINE -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ITERATIVE_APPLY -> AGGREGATION`
- 机械 flags: canon_multiset_equal=True; canon_sym_diff_n=0; number_sym_diff_n=12; families_equal=True; datasets_exact_differ=False; ui_delta=1; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S027 [diff/reorder_refactor_candidate] J=0.7778
- scripts: `script_109923` vs `script_137561` | sha_equal=False | diff_lines=6268
- RLE A(34步): `RASTER_LOAD -> GEOMETRY_DEFINE -> ATTRIBUTE_FILTER -> GEOMETRY_DEFINE -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_FILTER -> ATTRIBUTE_…`
- RLE B(34步): `RASTER_LOAD -> ATTRIBUTE_FILTER -> GEOMETRY_DEFINE -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> VECTOR_LO…`
- 机械 flags: canon_multiset_equal=True; canon_sym_diff_n=0; number_sym_diff_n=0; families_equal=True; datasets_exact_differ=False; ui_delta=3; dup_delta=10
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S028 [diff/reorder_refactor_candidate] J=0.7619
- scripts: `script_99819` vs `script_99816` | sha_equal=False | diff_lines=411
- RLE A(9步): `RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION -> BAND_ARITHMETIC -> CLASSIFICATION -> AGGREGATION -> RASTER_LOAD`
- RLE B(10步): `RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> RASTER_LOAD -> AGGREGATION -> BAND_ARITHMETIC -> CLASSIFICATION -> AGGREGATION -> RASTER_LOAD`
- 机械 flags: canon_multiset_equal=True; canon_sym_diff_n=0; number_sym_diff_n=2; families_equal=True; datasets_exact_differ=False; ui_delta=1; dup_delta=4
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S029 [diff/reorder_refactor_candidate] J=0.7805
- scripts: `script_170688` vs `script_249991` | sha_equal=False | diff_lines=290
- RLE A(11步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> CLASSIFICATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> CLASSI…`
- RLE B(4步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> CLASSIFICATION`
- 机械 flags: canon_multiset_equal=True; canon_sym_diff_n=0; number_sym_diff_n=3; families_equal=False; datasets_exact_differ=True; ui_delta=1; dup_delta=11
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S030 [diff/small_literal_cosmetic_candidate] J=0.7818
- scripts: `script_148097` vs `script_148112` | sha_equal=False | diff_lines=68
- RLE A(37步): `TEMPORAL_FILTER -> AGGREGATION -> OTHER_UNMAPPED -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> BAND_SELECT -> TEMPORAL_FILTER -> RASTER_LOAD -> THRESH…`
- RLE B(41步): `TEMPORAL_FILTER -> AGGREGATION -> OTHER_UNMAPPED -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> BAND_SELECT -> TEMPORAL_FILTER -> RASTER_LOAD -> THRESH…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=6; families_equal=False; datasets_exact_differ=True; ui_delta=0; dup_delta=5
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S031 [diff/small_literal_cosmetic_candidate] J=0.8333
- scripts: `script_16222` vs `script_68816` | sha_equal=False | diff_lines=9
- RLE A(6步): `RASTER_LOAD -> ATTRIBUTE_FILTER -> SPATIAL_FILTER -> TEMPORAL_FILTER -> BAND_ARITHMETIC -> AGGREGATION`
- RLE B(7步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> ATTRIBUTE_FILTER -> SPATIAL_FILTER -> TEMPORAL_FILTER -> BAND_ARITHMETIC -> AGGREGATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=2; families_equal=False; datasets_exact_differ=True; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S032 [diff/small_literal_cosmetic_candidate] J=0.9079
- scripts: `script_277481` vs `script_209898` | sha_equal=False | diff_lines=9
- RLE A(6步): `VECTOR_LOAD -> VECTOR_GEOMETRY -> RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> AGGREGATION`
- RLE B(7步): `VECTOR_LOAD -> VECTOR_GEOMETRY -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> AGGREGATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=2; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S033 [diff/small_literal_cosmetic_candidate] J=0.8254
- scripts: `script_45670` vs `script_45675` | sha_equal=False | diff_lines=60
- RLE A(5步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> GEOMETRY_DEFINE -> AGGREGATION`
- RLE B(7步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> GEOMETRY_DEFINE -> AGGREGATION -> GEOMETRY_DEFINE -> AGGREGATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=1; families_equal=True; datasets_exact_differ=False; ui_delta=7; dup_delta=3
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S034 [diff/small_literal_cosmetic_candidate] J=0.8548
- scripts: `script_145186` vs `script_145241` | sha_equal=False | diff_lines=62
- RLE A(70步): `RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> SPA…`
- RLE B(68步): `RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> SPA…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=4; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S035 [diff/small_literal_cosmetic_candidate] J=0.8636
- scripts: `script_213788` vs `script_213790` | sha_equal=False | diff_lines=25
- RLE A(9步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> AGGREGATION -> CLASSIFICATION -> BAND_ARITHMETIC -> AGGREGATION`
- RLE B(10步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> AGGREGATION -> ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> AGGREGATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=2; number_sym_diff_n=4; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S036 [diff/small_literal_cosmetic_candidate] J=0.898
- scripts: `script_145163` vs `script_145258` | sha_equal=False | diff_lines=62
- RLE A(70步): `RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> SPA…`
- RLE B(68步): `RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> SPA…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=2; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S037 [diff/small_literal_cosmetic_candidate] J=0.7551
- scripts: `script_113158` vs `script_113160` | sha_equal=False | diff_lines=15
- RLE A(25步): `RASTER_LOAD -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_FILTER -> TEMPORAL_FI…`
- RLE B(21步): `RASTER_LOAD -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_FILTER -> TEMPORAL_FI…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=0; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=1
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S038 [diff/small_literal_cosmetic_candidate] J=0.9821
- scripts: `script_109366` vs `script_109367` | sha_equal=False | diff_lines=348
- RLE A(6步): `RASTER_LOAD -> SPATIAL_FILTER -> CLASSIFICATION -> ATTRIBUTE_FILTER -> CLASSIFICATION -> VECTOR_LOAD`
- RLE B(5步): `RASTER_LOAD -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION -> VECTOR_LOAD`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=1; families_equal=True; datasets_exact_differ=False; ui_delta=1; dup_delta=7
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S039 [diff/small_literal_cosmetic_candidate] J=0.8
- scripts: `script_211895` vs `script_211910` | sha_equal=False | diff_lines=23
- RLE A(5步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(4步): `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=5; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: a[数据集缺:landsat\s*5]; b[数据集缺:landsat\s*7]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S040 [diff/small_literal_cosmetic_candidate] J=0.8
- scripts: `script_80237` vs `script_80223` | sha_equal=False | diff_lines=157
- RLE A(12步): `RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> TEMPORAL_FILTER -> ITERATIVE_APPLY -> SPATIAL_FILTER -> RASTER_LOAD -> BAND_SELECT -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> AGG…`
- RLE B(10步): `RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> TEMPORAL_FILTER -> ITERATIVE_APPLY -> SPATIAL_FILTER -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> AGGREGATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=5; families_equal=True; datasets_exact_differ=True; ui_delta=0; dup_delta=5
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S041 [diff/small_literal_cosmetic_candidate] J=0.8556
- scripts: `script_236072` vs `script_236022` | sha_equal=False | diff_lines=13
- RLE A(6步): `VECTOR_LOAD -> GEOMETRY_DEFINE -> RASTER_LOAD -> BAND_SELECT -> AGGREGATION -> BAND_ARITHMETIC`
- RLE B(5步): `VECTOR_LOAD -> RASTER_LOAD -> BAND_SELECT -> AGGREGATION -> BAND_ARITHMETIC`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=5; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S042 [diff/substantive_structural_candidate] J=0.8969
- scripts: `script_231951` vs `script_231952` | sha_equal=False | diff_lines=1047
- RLE A(19步): `RASTER_LOAD -> BAND_SELECT -> NEIGHBORHOOD -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> TEMPORAL_FILTER -> RA…`
- RLE B(18步): `RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> TEMPORAL_FILTER -> RASTER_LOAD -> BAN…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=2; number_sym_diff_n=10; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: b[数缺:2.5]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S043 [diff/substantive_structural_candidate] J=0.8313
- scripts: `script_265104` vs `script_265105` | sha_equal=False | diff_lines=41
- RLE A(7步): `VECTOR_LOAD -> RASTER_LOAD -> TEMPORAL_FILTER -> ITERATIVE_APPLY -> SPATIAL_FILTER -> AGGREGATION -> VECTOR_LOAD`
- RLE B(10步): `VECTOR_LOAD -> RASTER_LOAD -> TEMPORAL_FILTER -> ITERATIVE_APPLY -> SPATIAL_FILTER -> AGGREGATION -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> SPATIAL_JOIN -> VECTOR_LOAD`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=5; number_sym_diff_n=0; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=1
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S044 [diff/substantive_structural_candidate] J=0.7941
- scripts: `script_152529` vs `script_152447` | sha_equal=False | diff_lines=77
- RLE A(23步): `VECTOR_LOAD -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> THRESHOLD_LOGIC -> RASTER_LOAD -> THRESHOLD_LOGIC -> AGGREGATION -> RASTER_LOAD -> THR…`
- RLE B(30步): `VECTOR_LOAD -> RASTER_LOAD -> ATTRIBUTE_FILTER -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGRE…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=4; number_sym_diff_n=37; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S045 [diff/substantive_structural_candidate] J=0.8654
- scripts: `script_994` vs `script_976` | sha_equal=False | diff_lines=114
- RLE A(10步): `VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> BAND_ARITHMETIC -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(7步): `VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ITERATIVE_APPLY -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=7; number_sym_diff_n=43; families_equal=True; datasets_exact_differ=False; ui_delta=1; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S046 [diff/substantive_structural_candidate] J=0.7674
- scripts: `script_129577` vs `script_129575` | sha_equal=False | diff_lines=626
- RLE A(14步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> COLLECTION_MGMT -> AGGREGATION -> RASTER_LOAD -> BAND_ARI…`
- RLE B(15步): `AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> COLLECTION_MGMT -> AGGREGATION -> RASTER_L…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=15; families_equal=False; datasets_exact_differ=True; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S047 [diff/substantive_structural_candidate] J=0.7778
- scripts: `script_293907` vs `script_166973` | sha_equal=False | diff_lines=35
- RLE A(13步): `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> AGGREGATION -…`
- RLE B(20步): `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGREGATI…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=3; number_sym_diff_n=8; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S048 [diff/substantive_structural_candidate] J=0.7642
- scripts: `script_231953` vs `script_231946` | sha_equal=False | diff_lines=1281
- RLE A(23步): `RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> TEMPORA…`
- RLE B(27步): `RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> NEIGHBORHOOD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER ->…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=7; number_sym_diff_n=32; families_equal=False; datasets_exact_differ=True; ui_delta=2; dup_delta=2
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S049 [diff/substantive_structural_candidate] J=0.76
- scripts: `script_130615` vs `script_130620` | sha_equal=False | diff_lines=68
- RLE A(8步): `RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`
- RLE B(11步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOA…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=4; number_sym_diff_n=10; families_equal=False; datasets_exact_differ=True; ui_delta=0; dup_delta=1
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S050 [diff/substantive_structural_candidate] J=0.8125
- scripts: `script_127247` vs `script_127245` | sha_equal=False | diff_lines=2824
- RLE A(73步): `RASTER_LOAD -> BAND_ARITHMETIC -> ATTRIBUTE_FILTER -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -…`
- RLE B(68步): `RASTER_LOAD -> BAND_ARITHMETIC -> ATTRIBUTE_FILTER -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=6; number_sym_diff_n=3; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=2
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S051 [diff/substantive_structural_candidate] J=0.7576
- scripts: `script_52924` vs `script_52910` | sha_equal=False | diff_lines=19
- RLE A(12步): `ATTRIBUTE_FILTER -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> NEIGHBORHOOD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER -> AGGREG…`
- RLE B(11步): `AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> NEIGHBORHOOD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER -> AGGREGATION -> VECTOR_LOAD`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=9; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S052 [diff/substantive_structural_candidate] J=0.8434
- scripts: `script_253401` vs `script_253403` | sha_equal=False | diff_lines=81
- RLE A(5步): `RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> AGGREGATION -> VECTOR_LOAD`
- RLE B(7步): `RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> AGGREGATION -> VECTOR_LOAD`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=24; families_equal=False; datasets_exact_differ=True; ui_delta=0; dup_delta=4
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S053 [diff/substantive_structural_candidate] J=0.7586
- scripts: `script_129524` vs `script_129527` | sha_equal=False | diff_lines=21
- RLE A(10步): `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`
- RLE B(8步): `RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> VECTOR_LOAD`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=3; number_sym_diff_n=3; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S054 [diff/template_multiplicity_artifact] J=0.7627
- scripts: `script_17869` vs `script_69799` | sha_equal=False | diff_lines=23
- RLE A(16步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> TERRAIN_DERIVED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -…`
- RLE B(16步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> TERRAIN_DERIVED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -…`
- 机械 flags: canon_multiset_equal=True; canon_sym_diff_n=0; number_sym_diff_n=12; families_equal=False; datasets_exact_differ=True; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S055 [diff/template_multiplicity_artifact] J=0.7818
- scripts: `script_69799` vs `script_3327` | sha_equal=False | diff_lines=23
- RLE A(16步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> TERRAIN_DERIVED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -…`
- RLE B(16步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> TERRAIN_DERIVED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -…`
- 机械 flags: canon_multiset_equal=True; canon_sym_diff_n=0; number_sym_diff_n=7; families_equal=False; datasets_exact_differ=True; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S056 [diff/template_multiplicity_artifact] J=0.95
- scripts: `script_109918` vs `script_109917` | sha_equal=False | diff_lines=113
- RLE A(123步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTR…`
- RLE B(123步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_JOIN -> ATTR…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=0; number_sym_diff_n=10; families_equal=True; datasets_exact_differ=False; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S057 [diff/template_multiplicity_artifact] J=0.8077
- scripts: `script_69799` vs `script_17871` | sha_equal=False | diff_lines=29
- RLE A(16步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> TERRAIN_DERIVED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -…`
- RLE B(15步): `RASTER_LOAD -> TERRAIN_DERIVED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC ->…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=7; families_equal=False; datasets_exact_differ=True; ui_delta=0; dup_delta=0
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S058 [diff/ui_scaffold_candidate] J=0.7705
- scripts: `script_87903` vs `script_87898` | sha_equal=False | diff_lines=203
- RLE A(6步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> AGGREGATION -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(5步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=3; number_sym_diff_n=2; families_equal=True; datasets_exact_differ=False; ui_delta=3; dup_delta=24
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S059 [diff/ui_scaffold_candidate] J=0.8571
- scripts: `script_98866` vs `script_98857` | sha_equal=False | diff_lines=734
- RLE A(34步): `AGGREGATION -> GEOMETRY_DEFINE -> ATTRIBUTE_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> SPATIAL_…`
- RLE B(13步): `GEOMETRY_DEFINE -> ATTRIBUTE_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> AGGREGAT…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=9; number_sym_diff_n=7; families_equal=False; datasets_exact_differ=True; ui_delta=5; dup_delta=19
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S060 [diff/ui_scaffold_candidate] J=0.8333
- scripts: `script_109352` vs `script_131734` | sha_equal=False | diff_lines=414
- RLE A(14步): `RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> TERRAIN_DERIVED -> AGGREGATION -> TERRAIN_DERIVED -> REGIONAL_STATS -> TERRAIN_DERIVED -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGA…`
- RLE B(28步): `RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> TERRAIN_DERIVED -> AGGREGATION -> TERRAIN_DERIVED -> REGIONAL_STATS -> TERRAIN_DERIVED -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGA…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=15; number_sym_diff_n=45; families_equal=True; datasets_exact_differ=False; ui_delta=3; dup_delta=5
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S061 [diff/ui_scaffold_candidate] J=0.7885
- scripts: `script_109927` vs `script_137561` | sha_equal=False | diff_lines=7236
- RLE A(82步): `RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> RASTER_LOAD -> SPAT…`
- RLE B(34步): `RASTER_LOAD -> ATTRIBUTE_FILTER -> GEOMETRY_DEFINE -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> VECTOR_LO…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=3; number_sym_diff_n=121; families_equal=False; datasets_exact_differ=True; ui_delta=35; dup_delta=349
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S062 [diff/ui_scaffold_candidate] J=0.8372
- scripts: `script_23594` vs `script_23960` | sha_equal=False | diff_lines=18506
- RLE A(28步): `RASTER_LOAD -> MASKING -> RASTER_LOAD -> MASKING -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> MASKING -> RASTER_LOAD -> MASKING -> RASTER_LOAD -> B…`
- RLE B(27步): `RASTER_LOAD -> MASKING -> RASTER_LOAD -> BAND_SELECT -> MASKING -> RASTER_LOAD -> BAND_SELECT -> MASKING -> RASTER_LOAD -> MASKING -> RASTER_LOAD -> BAND_SELECT -> MASKING -> RASTE…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=1; number_sym_diff_n=54; families_equal=True; datasets_exact_differ=False; ui_delta=14; dup_delta=143
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S063 [diff/ui_scaffold_candidate] J=0.76
- scripts: `script_152314` vs `script_152326` | sha_equal=False | diff_lines=4231
- RLE A(8步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> BAND_SELECT -> CLASSIFICATION -> NEIGHBORHOOD`
- RLE B(12步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ITERATIVE_APPLY -> RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> CLASSIF…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=2; number_sym_diff_n=1301; families_equal=False; datasets_exact_differ=True; ui_delta=6; dup_delta=254
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S064 [diff/ui_scaffold_candidate] J=0.8182
- scripts: `script_101572` vs `script_101511` | sha_equal=False | diff_lines=235
- RLE A(11步): `ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION -> VECTOR_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> VECTOR_LOAD -> AGGREGATION -> VECTOR…`
- RLE B(13步): `ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION -> RASTER_LOAD -> VECTOR_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> VECTOR_LOAD -> AGGREG…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=2; number_sym_diff_n=34; families_equal=False; datasets_exact_differ=True; ui_delta=16; dup_delta=8
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S065 [diff/ui_scaffold_candidate] J=0.7963
- scripts: `script_45911` vs `script_45875` | sha_equal=False | diff_lines=278
- RLE A(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(10步): `RASTER_LOAD -> TEMPORAL_FILTER -> RASTER_LOAD -> TEMPORAL_FILTER -> ITERATIVE_APPLY -> AGGREGATION -> RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=3; number_sym_diff_n=21; families_equal=False; datasets_exact_differ=True; ui_delta=4; dup_delta=18
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S066 [diff/ui_scaffold_candidate] J=0.8136
- scripts: `script_244602` vs `script_169585` | sha_equal=False | diff_lines=1837
- RLE A(42步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> CLOUD_PROCESS -> BAND_SELECT -> AGGREGATION -> RASTER_LOAD -> AGGREGATION -> NEIGHBORHOOD -> RASTER_LOAD -> …`
- RLE B(41步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION -> RASTER_LOAD -> AGGREGATION -> NEIGHBORHOOD -> RASTER_LOAD -> NEIGHBORHOOD -> AGGREGATION -> R…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=3; number_sym_diff_n=14; families_equal=True; datasets_exact_differ=False; ui_delta=17; dup_delta=18
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S067 [diff/ui_scaffold_candidate] J=0.9038
- scripts: `script_49241` vs `script_49237` | sha_equal=False | diff_lines=3015
- RLE A(65步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD…`
- RLE B(63步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=5; number_sym_diff_n=18; families_equal=True; datasets_exact_differ=False; ui_delta=41; dup_delta=68
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S068 [diff/ui_scaffold_candidate] J=0.8406
- scripts: `script_236615` vs `script_236626` | sha_equal=False | diff_lines=642
- RLE A(14步): `RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COLLECTION_MGMT -> ITERATIVE_APPLY -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> AGGREGAT…`
- RLE B(13步): `AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COLLECTION_MGMT -> ITERATIVE_APPLY -> RASTER_LOAD -> TEMPORAL_FILTER -> CLASSIFICAT…`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=3; number_sym_diff_n=61; families_equal=False; datasets_exact_differ=True; ui_delta=4; dup_delta=15
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S069 [diff/ui_scaffold_candidate] J=0.75
- scripts: `script_23567` vs `script_24716` | sha_equal=False | diff_lines=999
- RLE A(12步): `RASTER_LOAD -> BAND_ARITHMETIC -> OTHER_UNMAPPED -> SPATIAL_CLIP -> RASTER_LOAD -> SPATIAL_CLIP -> THRESHOLD_LOGIC -> ITERATIVE_APPLY -> RASTER_LOAD -> VECTOR_LOAD -> RASTER_LOAD -…`
- RLE B(9步): `RASTER_LOAD -> SPATIAL_CLIP -> THRESHOLD_LOGIC -> ITERATIVE_APPLY -> RASTER_LOAD -> VECTOR_LOAD -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD`
- 机械 flags: canon_multiset_equal=False; canon_sym_diff_n=2; number_sym_diff_n=11; families_equal=True; datasets_exact_differ=False; ui_delta=13; dup_delta=32
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S070 [same/formatting_only] J=0.8148
- scripts: `script_87537` vs `script_19911` | sha_equal=False | diff_lines=453
- RLE A(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S071 [same/formatting_only] J=0.9333
- scripts: `script_121094` vs `script_121103` | sha_equal=False | diff_lines=149
- RLE A(13步): `RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> AGGREGATION -> BAND_ARITHMETIC -> GEOMETRY_DEFINE -> VECTOR_LOAD -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC ->…`
- RLE B(13步): `RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> AGGREGATION -> BAND_ARITHMETIC -> GEOMETRY_DEFINE -> VECTOR_LOAD -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC ->…`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S072 [same/formatting_only] J=0.8202
- scripts: `script_255153` vs `script_291890` | sha_equal=False | diff_lines=28
- RLE A(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S073 [same/formatting_only] J=0.9878
- scripts: `script_213788` vs `script_213794` | sha_equal=False | diff_lines=5
- RLE A(9步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> AGGREGATION -> CLASSIFICATION -> BAND_ARITHMETIC -> AGGREGATION`
- RLE B(9步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> BAND_SELECT -> AGGREGATION -> CLASSIFICATION -> BAND_ARITHMETIC -> AGGREGATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S074 [same/formatting_only] J=0.7556
- scripts: `script_9727` vs `script_45393` | sha_equal=False | diff_lines=51
- RLE A(4步): `RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> AGGREGATION`
- RLE B(4步): `RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> AGGREGATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S075 [same/formatting_only] J=0.8295
- scripts: `script_179597` vs `script_243089` | sha_equal=False | diff_lines=22
- RLE A(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S076 [same/formatting_only] J=0.7658
- scripts: `script_405511` vs `script_403124` | sha_equal=False | diff_lines=28
- RLE A(3步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> AGGREGATION`
- RLE B(3步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> AGGREGATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S077 [same/formatting_only] J=0.7619
- scripts: `script_84504` vs `script_84457` | sha_equal=False | diff_lines=8
- RLE A(4步): `AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC`
- RLE B(4步): `AGGREGATION -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S078 [same/formatting_only] J=0.8696
- scripts: `script_71197` vs `script_71212` | sha_equal=False | diff_lines=8
- RLE A(5步): `ATTRIBUTE_FILTER -> CLASSIFICATION -> ATTRIBUTE_FILTER -> AGGREGATION -> VECTOR_LOAD`
- RLE B(5步): `ATTRIBUTE_FILTER -> CLASSIFICATION -> ATTRIBUTE_FILTER -> AGGREGATION -> VECTOR_LOAD`
- 机械 flags: —
- 保真度提名: a[数据集缺:landsat\s*8]; b[数据集缺:landsat\s*8]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S079 [same/formatting_only] J=0.8125
- scripts: `script_287326` vs `script_174756` | sha_equal=False | diff_lines=204
- RLE A(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S080 [same/formatting_only] J=0.8222
- scripts: `script_65791` vs `script_65770` | sha_equal=False | diff_lines=5
- RLE A(8步): `VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> AGGREGATION -> CLASSIFICATION`
- RLE B(8步): `VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> ITERATIVE_APPLY -> AGGREGATION -> CLASSIFICATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S081 [same/formatting_only] J=0.8415
- scripts: `script_179597` vs `script_262184` | sha_equal=False | diff_lines=32
- RLE A(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> BAND_SELECT -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S082 [same/same_code_two_descriptions] J=0.789
- scripts: `script_402532` vs `script_402547` | sha_equal=True | diff_lines=0
- RLE A(44步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_CLIP -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_CLIP -> BAND…`
- RLE B(44步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_CLIP -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_CLIP -> BAND…`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S083 [same/same_code_two_descriptions] J=0.9516
- scripts: `script_203560` vs `script_185722` | sha_equal=True | diff_lines=0
- RLE A(3步): `RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION`
- RLE B(3步): `RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S084 [same/same_code_two_descriptions] J=0.7714
- scripts: `script_289209` vs `script_289239` | sha_equal=True | diff_lines=0
- RLE A(6步): `GEOMETRY_DEFINE -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION`
- RLE B(6步): `GEOMETRY_DEFINE -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S085 [same/same_code_two_descriptions] J=0.9302
- scripts: `script_84772` vs `script_84828` | sha_equal=True | diff_lines=0
- RLE A(16步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> NEIGHBORHOOD -> …`
- RLE B(16步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> NEIGHBORHOOD -> …`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S086 [same/same_code_two_descriptions] J=0.8384
- scripts: `script_402552` vs `script_402511` | sha_equal=True | diff_lines=0
- RLE A(33步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> SPATIAL_CLIP -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_F…`
- RLE B(33步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> SPATIAL_CLIP -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_F…`
- 机械 flags: —
- 保真度提名: b[数缺:18]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S087 [same/same_code_two_descriptions] J=0.8261
- scripts: `script_400284` vs `script_401293` | sha_equal=True | diff_lines=0
- RLE A(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> AGGREGATION`
- RLE B(6步): `RASTER_LOAD -> TEMPORAL_FILTER -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> TEMPORAL_FILTER -> AGGREGATION`
- 机械 flags: —
- 保真度提名: a[数缺:32.19,48.76]; b[数缺:32.19,48.76]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S088 [same/same_code_two_descriptions] J=0.7667
- scripts: `script_405876` vs `script_411174` | sha_equal=True | diff_lines=0
- RLE A(6步): `GEOMETRY_DEFINE -> VECTOR_LOAD -> RASTER_LOAD -> CLASSIFICATION -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(6步): `GEOMETRY_DEFINE -> VECTOR_LOAD -> RASTER_LOAD -> CLASSIFICATION -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S089 [same/same_code_two_descriptions] J=0.7831
- scripts: `script_402765` vs `script_400263` | sha_equal=True | diff_lines=0
- RLE A(6步): `RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> AGGREGATION`
- RLE B(6步): `RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> AGGREGATION`
- 机械 flags: —
- 保真度提名: a[数缺:33.57,52.92]; b[数缺:33.57,52.92]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S090 [same/same_code_two_descriptions] J=0.7876
- scripts: `script_402494` vs `script_402531` | sha_equal=True | diff_lines=0
- RLE A(33步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> SPATIAL_CLIP -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_F…`
- RLE B(33步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> SPATIAL_CLIP -> VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_F…`
- 机械 flags: —
- 保真度提名: b[数缺:18]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S091 [same/same_code_two_descriptions] J=0.7742
- scripts: `script_183850` vs `script_183861` | sha_equal=True | diff_lines=0
- RLE A(7步): `RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_CLIP -> RASTER_LOAD -> AGGREGATION`
- RLE B(7步): `RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_CLIP -> RASTER_LOAD -> AGGREGATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S092 [same/same_code_two_descriptions] J=0.7532
- scripts: `script_219822` vs `script_219821` | sha_equal=True | diff_lines=0
- RLE A(56步): `RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> THRESHOLD_LOGIC -> ITERATIVE_APPLY -> RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> THRESHOLD_LOGIC -> ITERATIVE_APPLY -> RAST…`
- RLE B(56步): `RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> THRESHOLD_LOGIC -> ITERATIVE_APPLY -> RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> THRESHOLD_LOGIC -> ITERATIVE_APPLY -> RAST…`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S093 [same/same_code_two_descriptions] J=0.7667
- scripts: `script_215911` vs `script_215898` | sha_equal=True | diff_lines=0
- RLE A(6步): `VECTOR_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION`
- RLE B(6步): `VECTOR_LOAD -> BAND_ARITHMETIC -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S094 [same/same_template_canonical_diff] J=0.7595
- scripts: `script_154411` vs `script_154408` | sha_equal=False | diff_lines=5
- RLE A(5步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COLLECTION_MGMT -> CLASSIFICATION`
- RLE B(5步): `RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COLLECTION_MGMT -> CLASSIFICATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S095 [same/same_template_canonical_diff] J=0.7857
- scripts: `script_24714` vs `script_23548` | sha_equal=False | diff_lines=1009
- RLE A(9步): `RASTER_LOAD -> SPATIAL_CLIP -> THRESHOLD_LOGIC -> ITERATIVE_APPLY -> RASTER_LOAD -> VECTOR_LOAD -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD`
- RLE B(9步): `RASTER_LOAD -> SPATIAL_CLIP -> THRESHOLD_LOGIC -> ITERATIVE_APPLY -> RASTER_LOAD -> VECTOR_LOAD -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S096 [same/same_template_canonical_diff] J=0.902
- scripts: `script_186175` vs `script_187237` | sha_equal=False | diff_lines=17
- RLE A(1步): ``
- RLE B(1步): ``
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S097 [same/same_template_canonical_diff] J=0.7544
- scripts: `script_109902` vs `script_109898` | sha_equal=False | diff_lines=62
- RLE A(12步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> THRESHOLD_LOGIC -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> AGGREGAT…`
- RLE B(12步): `ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> THRESHOLD_LOGIC -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> SPATIAL_JOIN -> ATTRIBUTE_FILTER -> RASTER_LOAD -> AGGREGAT…`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S098 [same/same_template_canonical_diff] J=0.942
- scripts: `script_186250` vs `script_194398` | sha_equal=False | diff_lines=21
- RLE A(9步): `RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> AGGREGATION -> BAND_SELECT -> AGGREGATION`
- RLE B(9步): `RASTER_LOAD -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD -> BAND_SELECT -> TEMPORAL_FILTER -> AGGREGATION -> BAND_SELECT -> AGGREGATION`
- 机械 flags: —
- 保真度提名: a[数缺:8]; b[数缺:8]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S099 [same/same_template_canonical_diff] J=0.9143
- scripts: `script_147902` vs `script_77491` | sha_equal=False | diff_lines=148
- RLE A(14步): `RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> TERRAIN_DERIVED -> AGGREGATION -> TERRAIN_DERIVED -> REGIONAL_STATS -> TERRAIN_DERIVED -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGA…`
- RLE B(14步): `RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> TERRAIN_DERIVED -> AGGREGATION -> TERRAIN_DERIVED -> REGIONAL_STATS -> TERRAIN_DERIVED -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGA…`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S100 [same/same_template_canonical_diff] J=0.84
- scripts: `script_131053` vs `script_131074` | sha_equal=False | diff_lines=47
- RLE A(1步): `CLASSIFICATION`
- RLE B(1步): `CLASSIFICATION`
- 机械 flags: —
- 保真度提名: a[数据集缺:landsat\s*8]; b[数据集缺:landsat\s*8]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S101 [same/same_template_canonical_diff] J=0.85
- scripts: `script_23477` vs `script_23475` | sha_equal=False | diff_lines=515
- RLE A(19步): `RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> BAND_SELECT -> OTHER_UNMAPPED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER…`
- RLE B(19步): `RASTER_LOAD -> SPATIAL_CLIP -> RASTER_LOAD -> BAND_SELECT -> OTHER_UNMAPPED -> RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> AGGREGATION -> RASTER_LOAD -> SPATIAL_CLIP -> RASTER…`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S102 [same/same_template_canonical_diff] J=0.76
- scripts: `script_30704` vs `script_30698` | sha_equal=False | diff_lines=11
- RLE A(3步): `CLASSIFICATION -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(3步): `CLASSIFICATION -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: —
- 保真度提名: a[数据集缺:landsat\s*8]; b[数据集缺:landsat\s*8]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S103 [same/same_template_canonical_diff] J=0.7614
- scripts: `script_65642` vs `script_65640` | sha_equal=False | diff_lines=30
- RLE A(19步): `RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ITERATIVE_APPLY -> BAND_SELECT -> RASTER_LOAD -> BAND_ARITH…`
- RLE B(19步): `RASTER_LOAD -> BAND_ARITHMETIC -> RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ITERATIVE_APPLY -> BAND_SELECT -> RASTER_LOAD -> BAND_ARITH…`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S104 [same/same_template_canonical_diff] J=0.82
- scripts: `script_71201` vs `script_71206` | sha_equal=False | diff_lines=14
- RLE A(5步): `ATTRIBUTE_FILTER -> CLASSIFICATION -> ATTRIBUTE_FILTER -> AGGREGATION -> VECTOR_LOAD`
- RLE B(5步): `ATTRIBUTE_FILTER -> CLASSIFICATION -> ATTRIBUTE_FILTER -> AGGREGATION -> VECTOR_LOAD`
- 机械 flags: —
- 保真度提名: a[数据集缺:landsat\s*8]; b[数据集缺:landsat\s*8]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S105 [same/same_template_canonical_diff] J=0.9155
- scripts: `script_26820` vs `script_26818` | sha_equal=False | diff_lines=11
- RLE A(9步): `ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> RASTER_LOAD`
- RLE B(9步): `ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> BAND_ARITHMETIC -> BAND_SELECT -> AGGREGATION -> RASTER_LOAD`
- 机械 flags: —
- 保真度提名: a[数据集缺:landsat\s*7]; b[数据集缺:landsat\s*7]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S106 [same/same_template_literal_diff] J=0.8551
- scripts: `script_211918` vs `script_211914` | sha_equal=False | diff_lines=17
- RLE A(4步): `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(4步): `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: —
- 保真度提名: a[数据集缺:landsat\s*7]; b[数据集缺:landsat\s*5]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S107 [same/same_template_literal_diff] J=0.8333
- scripts: `script_171771` vs `script_169539` | sha_equal=False | diff_lines=5
- RLE A(7步): `TERRAIN_DERIVED -> BAND_ARITHMETIC -> TERRAIN_DERIVED -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC`
- RLE B(7步): `TERRAIN_DERIVED -> BAND_ARITHMETIC -> TERRAIN_DERIVED -> BAND_ARITHMETIC -> AGGREGATION -> RASTER_LOAD -> BAND_ARITHMETIC`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S108 [same/same_template_literal_diff] J=0.8627
- scripts: `script_145163` vs `script_145191` | sha_equal=False | diff_lines=16
- RLE A(70步): `RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> SPA…`
- RLE B(70步): `RASTER_LOAD -> TEMPORAL_FILTER -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> RASTER_LOAD -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> BAND_ARITHMETIC -> BAND_SELECT -> SPA…`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S109 [same/same_template_literal_diff] J=0.8636
- scripts: `script_101249` vs `script_101160` | sha_equal=False | diff_lines=5
- RLE A(7步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD`
- RLE B(7步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_ARITHMETIC -> TEMPORAL_FILTER -> AGGREGATION -> RASTER_LOAD`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S110 [same/same_template_literal_diff] J=0.7604
- scripts: `script_55526` vs `script_55520` | sha_equal=False | diff_lines=104
- RLE A(3步): `ATTRIBUTE_FILTER -> CLASSIFICATION -> AGGREGATION`
- RLE B(3步): `ATTRIBUTE_FILTER -> CLASSIFICATION -> AGGREGATION`
- 机械 flags: —
- 保真度提名: a[数据集缺:landsat\s*8]; b[数据集缺:landsat\s*8]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S111 [same/same_template_literal_diff] J=0.8194
- scripts: `script_214722` vs `script_214719` | sha_equal=False | diff_lines=11
- RLE A(10步): `RASTER_LOAD -> SPATIAL_FILTER -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> COMPOSITE -> ATTRIBUTE_FILTER -> AGGREGATION -> NEIGHBORHOOD -> AGGREGATION`
- RLE B(10步): `RASTER_LOAD -> SPATIAL_FILTER -> COMPOSITE -> RASTER_LOAD -> SPATIAL_FILTER -> COMPOSITE -> ATTRIBUTE_FILTER -> AGGREGATION -> NEIGHBORHOOD -> AGGREGATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S112 [same/same_template_literal_diff] J=0.7895
- scripts: `script_211912` vs `script_211898` | sha_equal=False | diff_lines=11
- RLE A(4步): `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- RLE B(4步): `RASTER_LOAD -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> CLASSIFICATION`
- 机械 flags: —
- 保真度提名: a[数据集缺:landsat\s*5]; b[数据集缺:landsat\s*5]
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S113 [same/same_template_literal_diff] J=0.8704
- scripts: `script_38688` vs `script_38701` | sha_equal=False | diff_lines=5
- RLE A(62步): `VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> OTHER_UNM…`
- RLE B(62步): `VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> OTHER_UNM…`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S114 [same/same_template_literal_diff] J=0.7931
- scripts: `script_14882` vs `script_50691` | sha_equal=False | diff_lines=300
- RLE A(7步): `VECTOR_LOAD -> RASTER_LOAD -> COMPOSITE -> ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> AGGREGATION`
- RLE B(7步): `VECTOR_LOAD -> RASTER_LOAD -> COMPOSITE -> ATTRIBUTE_FILTER -> CLASSIFICATION -> BAND_ARITHMETIC -> AGGREGATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S115 [same/same_template_literal_diff] J=0.8333
- scripts: `script_38694` vs `script_38685` | sha_equal=False | diff_lines=5
- RLE A(62步): `VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> OTHER_UNM…`
- RLE B(62步): `VECTOR_LOAD -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> ATTRIBUTE_FILTER -> COLLECTION_MGMT -> RASTER_LOAD -> SPATIAL_FILTER -> TEMPORAL_FILTER -> COMPOSITE -> OTHER_UNM…`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S116 [same/same_template_literal_diff] J=0.8372
- scripts: `script_35319` vs `script_35318` | sha_equal=False | diff_lines=35
- RLE A(4步): `RASTER_LOAD -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION`
- RLE B(4步): `RASTER_LOAD -> SPATIAL_FILTER -> ATTRIBUTE_FILTER -> AGGREGATION`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）

## S117 [same/same_template_literal_diff] J=0.8723
- scripts: `script_96217` vs `script_96230` | sha_equal=False | diff_lines=12
- RLE A(17步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_CLIP -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> THRESHOLD_LOGIC…`
- RLE B(17步): `VECTOR_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> ATTRIBUTE_FILTER -> RASTER_LOAD -> BAND_SELECT -> SPATIAL_CLIP -> BAND_ARITHMETIC -> RASTER_LOAD -> BAND_SELECT -> THRESHOLD_LOGIC…`
- 机械 flags: —
- 保真度提名: 无
- 判读（差异来源）: ____　（保真度 A: ____ B: ____）
