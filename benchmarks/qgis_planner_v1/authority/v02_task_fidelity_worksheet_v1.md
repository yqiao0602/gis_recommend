# v0.2 Task Fidelity Worksheet v1 (21 surviving recovered DAGs)

Purpose: fix the ALLOWED scope of each task text BEFORE writing any text.
6 entries are subchain_scoped (task may describe only the recovered sub-chain).

| # | entry | scope | ops | size | source | anchor |
|---|---|---|---|---|---|---|
| 1 | `287be70f78` | subchain_scoped | 3 | native:extractbyattribute..native:dissolve | standard_v2 | L3_02_06_02 |
| 2 | `29be1d8053` | full_workflow | 2 | native:reprojectlayer..native:multiparttosingleparts | standard_v2 | L3_02_07_01 |
| 3 | `302f34cdd7` | full_workflow | 4 | native:fieldcalculator..native:buffer | standard_v2 | L3_02_01_01 |
| 4 | `361c5eb306` | full_workflow | 11 | native:buffer..native:fieldcalculator | standard_v2 | L3_02_01_01 |
| 5 | `429556807a` | full_workflow | 7 | native:dissolve..native:zonalstatisticsfb | standard_v2 | L3_02_03_05 |
| 6 | `4792105e9c` | full_workflow | 3 | native:reprojectlayer..native:multiparttosingleparts | standard_v2 | L3_02_05_11 |
| 7 | `4cb8772d44` | full_workflow | 2 | native:intersection..native:difference | standard_v2 | L3_02_02_01 |
| 8 | `55d364d9cd` | full_workflow | 5 | native:fieldcalculator..native:fieldcalculator | workflow | L3_01_02_06 |
| 9 | `5900c6409f` | full_workflow | 6 | gdal:rastercalculator..native:extractbylocation | textbook_strict | L3_03_03_A |
| 10 | `7a19dc431b` | full_workflow | 4 | gdal:warpreproject..native:zonalstatisticsfb | workflow_A | L3_03_05_02 |
| 11 | `81bbd4ba77` | subchain_scoped | 2 | native:clip..native:buffer | standard_v2 | L3_02_02_06 |
| 12 | `85e32230f1` | subchain_scoped | 2 | native:mergevectorlayers..native:reprojectlayer | standard_v2 | L3_01_03_04 |
| 13 | `8c87bab93c` | subchain_scoped | 4 | native:reprojectlayer..native:multiparttosingleparts | standard_v2 | L3_02_01_01 |
| 14 | `98b45c90e3` | full_workflow | 2 | native:clip..native:rastersampling | standard_v2 | L3_02_02_06 |
| 15 | `c5863951f3` | full_workflow | 2 | native:mergevectorlayers..native:multiparttosingleparts | github_merge | L3_02_07_01 |
| 16 | `d57f26d6bc` | full_workflow | 3 | native:buffer..native:buffer | github_merge | L3_02_01_01 |
| 17 | `debe9501a6` | full_workflow | 2 | native:deletecolumn..native:fieldcalculator | github_merge | L3_01_02_02 |
| 18 | `dec749a979` | full_workflow | 5 | gdal:polygonize..native:zonalstatistics | github_merge | L3_02_06_02 |
| 19 | `dfeda93ca5` | subchain_scoped | 2 | qgis:minimumboundinggeometry..native:extractvertices | standard_v2 | L3_02_05_12 |
| 20 | `f950402772` | subchain_scoped | 3 | native:reprojectlayer..native:extractspecificvertices | standard_v2 | L3_02_05_11 |
| 21 | `fc01749f30` | full_workflow | 5 | native:buffer..native:union | github_merge | L3_02_01_01 |
