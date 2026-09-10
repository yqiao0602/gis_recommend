# v0.2 Recovered DAG Review Packet v1 (24 entries, review_required)

Source: v02_action_gate_reconciliation_v1.json (census cbc8269). Nothing here is admitted.
Topology is a recorded fact, not an admission criterion (L3 deferred).

| # | DAG key | action | recs | size | topology | anchor (family) | covered | source root | task admission |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `287be70f78` | review_api_sidecar | 3 | two_to_three | linear | L3_02_06_02 (Extract by Attribute) | L3_02_03_05,L3_02_06_02 | standard_v2 | not_granted_pending_fidelity_gate |
| 2 | `dfeda93ca5` | review_api_sidecar | 3 | two_to_three | linear | L3_02_05_12 (Minimum Bounding Geometry) | L3_02_05_11,L3_02_05_12 | standard_v2 | not_granted_pending_fidelity_gate |
| 3 | `302f34cdd7` | review_api_sidecar | 3 | four_to_six | pure_branch | L3_02_01_01 (Buffer) | L3_01_02_06,L3_02_01_01,L3_02_06_03 | standard_v2 | not_granted_pending_fidelity_gate |
| 4 | `361c5eb306` | review_api_sidecar | 3 | seven_plus | pure_merge | L3_02_01_01 (Buffer) | L3_01_02_06,L3_02_01_01,L3_02_02_04 | standard_v2 | not_granted_pending_fidelity_gate |
| 5 | `81bbd4ba77` | review_api_sidecar | 9 | two_to_three | linear | L3_02_02_06 (Clip) | L3_02_01_01,L3_02_02_06 | standard_v2 | not_granted_pending_fidelity_gate |
| 6 | `85e32230f1` | review_api_sidecar | 3 | two_to_three | linear | L3_01_03_04 (Merge) | L3_01_03_04,L3_01_10_01 | standard_v2 | not_granted_pending_fidelity_gate |
| 7 | `cb16fe08fb` | review_api_sidecar | 3 | two_to_three | linear | L3_02_01_01 (Buffer) | L3_01_02_06,L3_02_01_01 | standard_v2 | not_granted_pending_fidelity_gate |
| 8 | `8c87bab93c` | review_api_sidecar | 3 | four_to_six | linear | L3_02_01_01 (Buffer) | L3_01_10_01,L3_02_01_01,L3_02_02_04,L3_02_07_01 | standard_v2 | not_granted_pending_fidelity_gate |
| 9 | `f950402772` | review_api_sidecar | 3 | two_to_three | pure_branch | L3_02_05_11 (Feature to Point) | L3_01_10_01,L3_02_05_11 | standard_v2 | not_granted_pending_fidelity_gate |
| 10 | `98b45c90e3` | review_api_sidecar | 3 | two_to_three | linear | L3_02_02_06 (Clip) | L3_02_02_06,L3_08_01_01 | standard_v2 | not_granted_pending_fidelity_gate |
| 11 | `4cb8772d44` | review_api_sidecar | 3 | two_to_three | linear | L3_02_02_01 (Intersect) | L3_02_02_01,L3_02_02_04 | standard_v2 | not_granted_pending_fidelity_gate |
| 12 | `429556807a` | review_api_sidecar | 9 | seven_plus | pure_branch | L3_02_03_05 (Collect Features) | L3_01_02_06,L3_01_09_03,L3_02_02_01,L3_02_03_05,L3_03_02_01 | standard_v2 | not_granted_pending_fidelity_gate |
| 13 | `29be1d8053` | review_api_sidecar | 9 | two_to_three | linear | L3_02_07_01 (Multipart to Singlepart) | L3_01_10_01,L3_02_07_01 | standard_v2 | not_granted_pending_fidelity_gate |
| 14 | `4792105e9c` | review_api_sidecar | 3 | two_to_three | linear | L3_02_05_11 (Feature to Point) | L3_01_10_01,L3_02_05_11,L3_02_07_01 | standard_v2 | not_granted_pending_fidelity_gate |
| 15 | `c4b53b68a2` | review_api_sidecar | 2 | two_to_three | linear | L3_02_01_01 (Buffer) | L3_02_01_01 | workflow | not_granted_pending_fidelity_gate |
| 16 | `55d364d9cd` | review_api_sidecar | 1 | four_to_six | linear | L3_01_02_06 (Calculate Field) | L3_01_02_06 | workflow | not_granted_pending_fidelity_gate |
| 17 | `7a19dc431b` | review_api_sidecar | 1 | four_to_six | hybrid | L3_03_05_02 (Reproject) | L3_01_10_01,L3_03_02_01,L3_03_03_A,L3_03_05_02 | workflow_A | not_granted_pending_fidelity_gate |
| 18 | `099e2c2db0` | review_api_sidecar | 1 | two_to_three | linear | L3_08_01_01 (Region-based Sample Extraction) | L3_08_01_01 | workflow_A | not_granted_pending_fidelity_gate |
| 19 | `debe9501a6` | review_api_sidecar | 1 | two_to_three | linear | L3_01_02_02 (Delete Field) | L3_01_02_02,L3_01_02_06 | github_merge | ? |
| 20 | `d57f26d6bc` | review_api_sidecar | 1 | two_to_three | linear | L3_02_01_01 (Buffer) | L3_02_01_01 | github_merge | ? |
| 21 | `fc01749f30` | review_api_sidecar | 1 | four_to_six | linear | L3_02_01_01 (Buffer) | L3_02_01_01,L3_02_02_02 | github_merge | ? |
| 22 | `dec749a979` | review_api_sidecar | 1 | four_to_six | linear | L3_02_06_02 (Extract by Attribute) | L3_01_02_06,L3_01_09_03,L3_02_06_02,L3_03_02_01 | github_merge | ? |
| 23 | `5900c6409f` | review_api_sidecar | 2 | four_to_six | pure_merge | L3_03_03_A (Arithmetic & Math) | L3_01_03_04,L3_01_09_03,L3_02_01_01,L3_02_02_02,L3_02_06_03,L3_03_03_A | textbook_strict | ? |
| 24 | `c5863951f3` | review_api_sidecar | 1 | two_to_three | linear | L3_02_07_01 (Multipart to Singlepart) | L3_01_03_04,L3_02_07_01 | github_merge | ? |

## Per-entry operator chains

**1. `287be70f78`** (review_api_sidecar, 3 record(s))
- operators: native:extractbyattribute -> native:extractbyattribute -> native:dissolve
- edges: [[0, 1], [1, 2]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000007.py` (standard_v2)
- original gate reason: structure_class=blocked_downstream_transform, control_flow=[], intermediate_transforms=[]

**2. `dfeda93ca5`** (review_api_sidecar, 3 record(s))
- operators: qgis:minimumboundinggeometry -> native:extractvertices
- edges: [[0, 1]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000439.py` (standard_v2)
- original gate reason: structure_class=blocked_downstream_transform, control_flow=[], intermediate_transforms=[]

**3. `302f34cdd7`** (review_api_sidecar, 3 record(s))
- operators: native:fieldcalculator[1,3] ; native:buffer[2] ; native:extractbylocation[] ; native:buffer[]
- edges: [[0, 1], [0, 3], [1, 2]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000478.py` (standard_v2)
- original gate reason: structure_class=blocked_custom_transform, control_flow=['for'], intermediate_transforms=['featureCount', 'print', 'format']

**4. `361c5eb306`** (review_api_sidecar, 3 record(s))
- operators: native:buffer[4] ; native:buffer[2] ; native:fieldcalculator[4] ; native:buffer[5] ; native:difference[5] ; native:difference[7] ; native:buffer[7] ; native:difference[8] ; native:difference[9] ; native:fieldcalculator[10] ; native:fieldcalculator[]
- edges: [[0, 4], [1, 2], [2, 4], [3, 5], [4, 5], [5, 7], [6, 7], [7, 8], [8, 9], [9, 10]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000588.py` (standard_v2)
- original gate reason: structure_class=unresolved, control_flow=[], intermediate_transforms=[]

**5. `81bbd4ba77`** (review_api_sidecar, 9 record(s))
- operators: native:clip -> native:buffer
- edges: [[0, 1]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000594.py` (standard_v2)
- original gate reason: structure_class=blocked_custom_transform, control_flow=['for', 'if'], intermediate_transforms=['addMapLayer', 'clone', 'setName', 'setSubsetString', 'defaultSymbol', 'geometryType']

**6. `85e32230f1`** (review_api_sidecar, 3 record(s))
- operators: native:mergevectorlayers -> native:reprojectlayer
- edges: [[0, 1]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000716.py` (standard_v2)
- original gate reason: structure_class=blocked_custom_transform, control_flow=[], intermediate_transforms=['addMapLayer', 'setName', 'edit', 'getFeatures', 'updateFeature', 'deleteAttributes']

**7. `cb16fe08fb`** (review_api_sidecar, 3 record(s))
- operators: native:fieldcalculator -> native:buffer
- edges: [[0, 1]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000734.py` (standard_v2)
- original gate reason: structure_class=blocked_custom_transform, control_flow=[], intermediate_transforms=['dict']

**8. `8c87bab93c`** (review_api_sidecar, 3 record(s))
- operators: native:reprojectlayer -> native:buffer -> native:difference -> native:multiparttosingleparts
- edges: [[0, 1], [1, 2], [2, 3]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000736.py` (standard_v2)
- original gate reason: structure_class=blocked_custom_transform, control_flow=['if'], intermediate_transforms=['addMapLayer', 'QgsVectorLayer', 'authid', 'crs', 'fields', 'addAttributes']

**9. `f950402772`** (review_api_sidecar, 3 record(s))
- operators: native:reprojectlayer[1,2] ; native:extractspecificvertices[] ; native:extractspecificvertices[]
- edges: [[0, 1], [0, 2]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000749.py` (standard_v2)
- original gate reason: structure_class=blocked_custom_transform, control_flow=[], intermediate_transforms=['mapLayerFromString', 'edit', 'addAttribute', 'indexFromName', 'fields', 'zip']

**10. `98b45c90e3`** (review_api_sidecar, 3 record(s))
- operators: native:clip -> native:rastersampling
- edges: [[0, 1]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000792.py` (standard_v2)
- original gate reason: structure_class=blocked_downstream_transform, control_flow=[], intermediate_transforms=[]

**11. `4cb8772d44`** (review_api_sidecar, 3 record(s))
- operators: native:intersection -> native:difference
- edges: [[0, 1]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000903.py` (standard_v2)
- original gate reason: structure_class=blocked_custom_transform, control_flow=['for'], intermediate_transforms=['QgsProcessingFeatureSourceDefinition']

**12. `429556807a`** (review_api_sidecar, 9 record(s))
- operators: native:dissolve[1] ; native:fieldcalculator[2,4] ; native:intersection[3] ; native:dissolve[5] ; gdal:rasterize[] ; native:zonalstatisticsfb[6] ; native:zonalstatisticsfb[]
- edges: [[0, 1], [1, 2], [1, 4], [2, 3], [3, 5], [5, 6]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000912.py` (standard_v2)
- original gate reason: structure_class=blocked_custom_transform, control_flow=['if'], intermediate_transforms=['QgsVectorLayer']

**13. `29be1d8053`** (review_api_sidecar, 9 record(s))
- operators: native:reprojectlayer -> native:multiparttosingleparts
- edges: [[0, 1]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000959.py` (standard_v2)
- original gate reason: structure_class=blocked_custom_transform, control_flow=['if'], intermediate_transforms=['isMultiType', 'wkbType']

**14. `4792105e9c`** (review_api_sidecar, 3 record(s))
- operators: native:reprojectlayer -> native:extractvertices -> native:multiparttosingleparts
- edges: [[0, 1], [1, 2]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\QGIS_standard_multi_operator_workflows_v2\downloaded_scripts\script_0000960.py` (standard_v2)
- original gate reason: structure_class=blocked_custom_transform, control_flow=['if'], intermediate_transforms=['geometryType', 'isMultiType', 'wkbType']

**15. `c4b53b68a2`** (review_api_sidecar, 2 record(s))
- operators: native:buffer -> native:buffer
- edges: [[0, 1]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\github_qgis_workflow\downloaded_scripts\script_0005758.py` (workflow)
- original gate reason: structure_class=blocked_custom_transform, control_flow=[], intermediate_transforms=['from_polygon_layer', 'transform', 'copy_geometries_back_to_layer']

**16. `55d364d9cd`** (review_api_sidecar, 1 record(s))
- operators: native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator -> native:fieldcalculator
- edges: [[0, 1], [1, 2], [2, 3], [3, 4]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\github_qgis_workflow\downloaded_scripts\script_0007946.py` (workflow)
- original gate reason: structure_class=blocked_downstream_transform, control_flow=[], intermediate_transforms=[]

**17. `7a19dc431b`** (review_api_sidecar, 1 record(s))
- operators: gdal:warpreproject[1] ; gdal:rastercalculator[2,3] ; native:reprojectlayer[3] ; native:zonalstatisticsfb[]
- edges: [[0, 1], [1, 2], [1, 3], [2, 3]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\github_qgis_workflow_A类\downloaded_scripts\script_0007090.py` (workflow_A)
- original gate reason: structure_class=blocked_custom_transform, control_flow=['for', 'if'], intermediate_transforms=['isinstance', 'source', 'append', 'pushInfo', 'mapLayerFromString', 'QgsRasterLayer']

**18. `099e2c2db0`** (review_api_sidecar, 1 record(s))
- operators: native:rastersampling -> native:rastersampling
- edges: [[0, 1]]
- first source: `E:\02_projects\03_PythonProject\Operator-recommend-system\Algorithm_classification\system_redesign\爬取GithubQGIS\github_qgis_workflow_A类\downloaded_scripts\script_0007495.py` (workflow_A)
- original gate reason: structure_class=blocked_downstream_transform, control_flow=[], intermediate_transforms=[]

**19. `debe9501a6`** (review_api_sidecar, 1 record(s))
- operators: native:deletecolumn -> native:fieldcalculator
- edges: [[0, 1]]
- first source: `/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts/script_37222.py` (github_merge)

**20. `d57f26d6bc`** (review_api_sidecar, 1 record(s))
- operators: native:buffer -> native:buffer -> native:buffer
- edges: [[0, 1], [1, 2]]
- first source: `/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts/script_31926.py` (github_merge)

**21. `fc01749f30`** (review_api_sidecar, 1 record(s))
- operators: native:buffer -> native:buffer -> native:buffer -> native:union -> native:union
- edges: [[0, 1], [1, 2], [2, 3], [3, 4]]
- first source: `/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts/script_31927.py` (github_merge)

**22. `dec749a979`** (review_api_sidecar, 1 record(s))
- operators: gdal:polygonize -> native:extractbyattribute -> native:fieldcalculator -> native:extractbyexpression -> native:zonalstatistics
- edges: [[0, 1], [1, 2], [2, 3], [3, 4]]
- first source: `/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts/script_6649.py` (github_merge)

**23. `5900c6409f`** (review_api_sidecar, 2 record(s))
- operators: gdal:rastercalculator[1] ; gdal:polygonize[3] ; native:buffer[3] ; native:mergevectorlayers[4] ; native:union[5] ; native:extractbylocation[]
- edges: [[0, 1], [1, 3], [2, 3], [3, 4], [4, 5]]
- first source: `/home/yll/GEE/爬取GIS代码/QGIS_ArcGIS_Textbook_Candidates_Broad/downloaded_scripts_strict/script_0006069.py` (textbook_strict)

**24. `c5863951f3`** (review_api_sidecar, 1 record(s))
- operators: native:mergevectorlayers -> native:multiparttosingleparts
- edges: [[0, 1]]
- first source: `/home/yll/GEE/爬取GithubQGIS/合并脚本/QGIS_merged_dedup_by_index/downloaded_scripts/script_41874.py` (github_merge)

