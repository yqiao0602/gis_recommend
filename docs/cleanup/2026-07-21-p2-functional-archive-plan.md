# P2 功能簇归档计划（2026-07-21）

## 目标

减少已跟踪的专利生成物、阶段性 shadow 测试和旧 GEE 数据管线对默认检索/测试的干扰，同时保持正式 CLI、当前 94-L3 Step8 契约和历史复现能力。

## 行为锁

- Shadow 历史测试：208项中205项通过；3项因直接执行测试文件时 `scripts` 命名空间不在导入路径而报错，不是断言失败。
- Legacy provenance：`test_pipeline_provenance.py` 8/8通过。
- Legacy Step3：`test_step3_deduplicate.py` 1/1通过。
- Mainline contract当前有1个环境/数据状态相关既有失败：期望缺失的I/O元数据在本机实际存在。

## Pass 1：专利中间物

- 迁移3个Office解包目录；
- 迁移5个无引用review媒体目录；
- 迁移编辑器备份、Word锁文件和临时文件；
- 排除当前modified/untracked稿件、最终提交稿、当前drawio源和成对历史审查材料；
- 生成SHA256清单。

## Pass 2：Shadow测试簇

- 保留正式`runner.py`、`report.py`、`run_contract.py`和`shadow_phase.py`；
- 将阶段性`test_mainline_shadow_phase.py`移入`experiments/shadow_evaluation/tests/`；
- 在默认`tests/`保留短版runtime smoke测试；
- 配置pytest默认只收集`tests/`。

## Pass 3：Legacy GEE管线

- 将Step1–8、pipeline runner和sequence cleaner主体移动到`src/gis_recommend/legacy/gee_pipeline/`；
- 原`gis_recommend.data.*`路径保留兼容wrapper；
- 保留`pipeline_provenance.py`、`run_v2_full_pipeline.sh`、Step8产物契约和当前provenance测试；
- 将危险旧`run_full_pipeline.sh`和迁移工具放入版本化legacy工具区，不删除。

## 检索与测试边界

- 新增`.rgignore`排除版本化归档、专利二进制/Office内部文件和实验目录；
- 在`pyproject.toml`配置pytest `testpaths`、`norecursedirs`和markers；
- 不新增依赖。

## 明确不做

- 不重构正式shadow报告schema；
- 不删除旧CLI兼容路径；
- 不修改模型、训练数据或taxonomy；
- 不触碰当前用户正在修改的专利材料。

## 执行结果

### 专利中间物

- 已归档164个tracked文件：3个Office解包目录、5个孤儿review媒体目录和12个编辑器/Word临时文件；
- 归档位置：`docs/archive/patent_intermediates/2026-07-21/`；
- SHA256清单：`docs/cleanup/2026-07-21-patent-intermediates-manifest.md`；
- 164/164哈希复核一致；当前modified/untracked专利材料未移动。

### Shadow测试簇

- 4615行历史测试迁入`experiments/shadow_evaluation/tests/`；
- 正式`runner.py`、`report.py`、`run_contract.py`、`shadow_phase.py`未移动；
- 默认测试新增3项runtime smoke并全部通过；
- 历史208项测试保留，可显式运行。

### Legacy GEE管线

- 10个Step1-8主体实现迁入`src/gis_recommend/legacy/gee_pipeline/`；
- 原`gis_recommend.data.*`路径保留薄wrapper；
- 危险旧`run_full_pipeline.sh`和旧产物迁移工具迁入`legacy/gee_pipeline/tools/`；
- Step3历史测试迁入`legacy/gee_pipeline/tests/`；
- compatibility 2/2、provenance 8/8、archived Step3 1/1通过；
- `python -m gis_recommend.data.pipeline_runner --help`和`python -m gis_recommend.evaluation --help`通过。

### 质量门禁

- `python -m compileall -q src scripts tests legacy experiments`通过；
- `.rgignore`排除版本化归档、实验目录、legacy实现和专利生成物；
- `pyproject.toml`已配置默认pytest收集边界和markers；
- 当前环境未安装pytest，未执行pytest形式的全仓收集。
