# QGIS 多步 Processing 依赖恢复复审（2026-07-23）

## 范围

本次只复审首批50条中的3条 dependency-only 记录：40、43、47。原
`pilot_v3_review_50_adjudicated_v1` 保持不变；新的复审 authority 位于：

`docs/reports/qgis_multistep_processing/pilot_dependency_recovery_rereview_3_v1/`

新增复审表 `review_50_dependency_recovered.csv` 仅将三行的 dependency
authority 更新为恢复后的证据，并保留其余47行原值。三条复审字段和任务
名称/描述写入 `adjudications_dependency_recovered.jsonl`。

## 复审结论

| review | 链 | 新依赖证据 | 结论 |
|---:|---|---|---|
| 40 | `difference -> buffer -> buffer -> clip` | 3 条 `parameter_binding` | accepted |
| 43 | `extractbyattribute -> 6 x zonalstatisticsfb` | 6 条 `parameter_binding` | accepted |
| 47 | `clip -> dissolve` | 1 条 `output_path_reference` | accepted |

三条均满足：workflow boundary、算子身份/顺序、依赖、重复调用语义、
stable-94 精确映射、任务完整性、描述生成准入和训练候选准入；均为唯一
记录，不属于簇内对照。描述只覆盖可由源码证明的 Processing 任务，未把
后续图层加载、属性编辑或其他非 Processing 副作用伪装成算子步骤。

## 新训练 authority

`pilot_dependency_recovery_rereview_3_v1/adjudicated_v2/`

- reviewed：50
- accepted：15（原12 + 本次3）
- deferred：17
- rejected：18
- training rows：15
- unique training semantic signatures：15
- review CSV SHA256：`1415916795701d8f1ace0a495a90e28593d7818b4e2ba38a00094b42f2669d26`

该 authority 仍未授予 taxonomy admission；不包含簇内对照、catalog miss、
动态/自定义未恢复链或低层 PyQGIS API。

## 验证

- 严格准入构建器：`reviewed=50 accepted=15 deferred=17 rejected=18 training_rows=15`
- V4 Dataset/主序列 loss CPU 冒烟：15/15 rows、4 batches、66 个非 PAD target、
  `mean_loss=4.584967136383057`、梯度全部有限、未写 checkpoint。
- 本机默认 Python 未安装 pytest，因此本轮没有重新运行 pytest；之前的
  `test_qgis*.py` 666/666 和多步专项38/38证据仍对应同一恢复代码版本。
