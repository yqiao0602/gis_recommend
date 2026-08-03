# QGIS Joern、Registry 与 DataTrove Pilot 设计

日期：2026-08-03

## 目标

在不修改现有 QGIS 正式训练 authority、不写入 `/home/yll`、不生成训练
JSONL 的前提下，验证 Joern、QGIS 3.28 Processing Registry 和 DataTrove
能否作为现有 QGIS source-to-training-data 流水线的可复现 sidecar，减少
Processing 跨函数恢复和低层 PyQGIS API 任务边界恢复中的手写静态分析工作。

首轮只处理 200 条目标源码：100 条 Processing blocker 和 100 条低层 API
deferred。现有冻结的 Processing accepted authority、API reviewed TP/TN、已知链
截断和语义续接负例作为额外回归基线，不计入 200 条目标样本。

## 非目标

- 不用 Joern 直接授予 `accepted` 或训练准入。
- 不用 QGIS Registry 自动决定项目自定义 L3 映射。
- 不用 DataTrove 替代 normalized AST、DAG、L3 序列和训练对四层去重。
- 不修改现有 283 条 Processing 正式交付或 API train-only authority。
- 不调用 LLM，不训练模型，不写 checkpoint，不生成生产训练 JSONL。
- 不全量重放 8,466 条 Processing 或 39,386 条 API 源码。

## 执行边界

试验运行在 Linux 服务器 `qy@10.191.2.38`。服务器已验证具备 Docker
29.1、Java 21、125 GiB 内存和约 370 GiB 可用磁盘。`/home/qy` 可写，
`/home/yll` 当前不可写并继续作为只读源码 authority。

所有服务器产物写入：

```text
/home/qy/system_redesign/diagnostics/qgis_joern_pilot_v1/
├── inputs/
├── joern/
├── qgis_registry/
├── datatrove/
├── comparison/
└── hashes/
```

本机只同步实现代码、小型 JSON/JSONL/CSV/Markdown 结果和哈希证据，不同步
容器层、Joern CPG、200 份源码副本或其他大型中间产物。

## 架构

### 1. 冻结输入

从现有 authority 按 normalized source body 分层选择：

- Processing 100 条：helper 传递、output alias、结果字典、动态 operator ID、
  `if/for` 和 missing data edges。
- API 100 条：跨函数 geometry/mutation/export、terminal sink 和 interleaved
  control flow。

选择器必须记录 record/unit ID、source path、source SHA256、normalized-body
authority、既有状态和分层标签。目标包内部不得有 normalized-body 重复；与作为
评估基线的冻结 holdout authority 不得交叉。对应源码从 `/home/yll` 只读复制到
`inputs/sources/`，复制后再次校验 SHA256。

### 2. Joern sidecar

Joern 使用官方容器和固定镜像 digest构建 Python Code Property Graph。查询只输出
证据，不输出训练决定。

Processing 查询族：

- `P1`：`processing.run()` 第一个参数的常量、别名、函数形参和返回值传播。
- `P2`：参数字典构造、更新、helper 传递和第二参数 backward slice。
- `P3`：`result["OUTPUT"]`、字典解包和 output alias 到后续 Processing 输入。
- `P4`：caller/callee、helper return 和 custom algorithm 内嵌 Processing 链。
- `P5`：控制路径、完整 dependency path 和 terminal 截断证据。

API 查询族：

- `A1`：PyQGIS geometry、raster、spatial-index 和 attribute 语义调用。
- `A2`：语义调用到 `setGeometry`、`addFeature`、writer 或 sink 的数据流。
- `A3`：跨函数参数和返回值传播。
- `A4`：以 terminal 为终点的 backward slice 任务边界。
- `A5`：分支冲突、外部 payload、未知调用和链截断证据。

每条 sidecar 记录必须包含 source SHA256、源码位置、Joern 节点 ID、source、sink、
完整 flow path、查询 ID 和查询版本。无路径、多条不兼容路径、外部调用无法解析或
query/runtime 失败时显式标记为 `deferred`，不得静默 fallback。

### 3. QGIS 3.28 Registry sidecar

QGIS 使用官方容器和固定镜像 digest。运行时通过 `qgis_process --json` 或等价
PyQGIS Registry API 导出：

- provider ID、provider 版本和可用状态；
- algorithm ID、display name 和帮助文本；
- 输入参数名称、类型、可选性和默认值；
- 输出名称和输出类型。

状态必须区分 `operator_not_found`、`provider_not_installed` 和
`provider_version_mismatch`。GRASS/SAGA provider 未包含在镜像时不得误记为 catalog
miss。Registry 快照用于 operator contract 验证，不自动创建或修改 L3 authority。

### 4. DataTrove sidecar

DataTrove 安装在 `/home/qy` 的独立、固定依赖版本 Python 环境中。它读取项目现有
normalized source body，而不是包含爬取头、路径注释和采集元数据的原始文本。

- exact 分组必须复现现有 normalized-body authority。
- MinHash 使用代码 token shingles 形成近重复簇。
- 每个簇保留成员 ID、source SHA256、相似度配置和 canonical 候选。
- MinHash 只生成审核 sidecar，不直接删除、合并或压制训练候选。

### 5. 对照报告

comparison driver 按稳定 ID 合并现有 verdict 与三类 sidecar，输出逐条 ledger、分层
混淆矩阵、链完整性差异、新恢复 family census、运行时间、峰值内存、磁盘使用和全池
资源预测。未命中的记录也必须保留，禁止只报告成功样本。

## 错误处理与可复现性

- 所有批处理先写临时文件，完成 schema、计数和哈希验证后再原子替换目标文件。
- 容器退出非零、输出缺失、JSON 无法解析、source SHA 不符或记录数变化均使该阶段
  fail closed；下游阶段不得消费不完整产物。
- 镜像名称、tag、digest、Joern/QGIS/DataTrove 版本、命令、代码 SHA、输入 SHA 和
  输出 SHA 写入 `hashes/run_manifest_v1.json`。
- `/home/yll` 仅以只读 bind mount或普通读取方式访问；任何安装、缓存和中间文件均
  写入 `/home/qy`。
- 运行可重复执行；相同输入、代码、镜像 digest和配置必须生成字节级一致的小型
  JSON/JSONL/CSV authority。CPG本体不要求字节级一致，但其查询导出必须排序和规范化。

## 验收门禁

硬门禁：

1. 200/200 目标源码 SHA256 回连成功。
2. 既有 accepted回归召回为 100%。
3. 已审核负例 FP=0。
4. 已知完整链的截断数为 0。
5. QGIS operator contract没有静默 fallback或 provider状态混算。
6. DataTrove exact cluster与现有 normalized-body authority一致。
7. 三类 sidecar均可由稳定 ID回连到源码、输入 authority和工具版本。

推广门禁：

- 至少一个此前 unresolved且 normalized-body support不低于 30 的 family完成
  source-disjoint calibration/holdout 双侧零 FP校准。
- 新 family仍需经过现有任务边界、L3、描述 fidelity和四层去重门禁；pilot本身不授予
  training admission。
- 全池运行时间和磁盘预测不得超过服务器可用资源；预测依据和测量方法必须进入报告。

若硬门禁失败，则保留失败证据并停止，不修改现有流水线。若硬门禁通过但没有达到推广
门禁，则正式结论为“工具可运行，但尚未证明能提高训练数据产量”，不得为采用工具而
放宽现有质量标准。

## 测试策略

- 单元测试：输入选择、source-disjoint、sidecar schema、状态枚举、稳定排序、原子写入
  和 DataTrove exact 对账。
- fixture集成测试：用小型 Python 源码覆盖 helper、返回值、结果字典、分支冲突、完整
  API-to-sink链和截断链。
- 容器 smoke：分别验证 Joern Python frontend、QGIS 3.28 Registry和 DataTrove版本，
  并记录镜像或环境 digest。
- 服务器 pilot：运行200条目标样本及额外冻结回归基线，生成comparison报告。
- 重复运行：对所有同步回本机的小型产物执行SHA256一致性检查。

## 交付物

本机同步并纳入版本化证据的产物限定为：

- 工具适配代码和测试；
- 200条选择 manifest，不含完整源码正文；
- Registry规范化快照或其必要子集；
- Joern规范化flow sidecar的小型摘要与哈希；
- DataTrove cluster ledger的小型摘要与哈希；
- comparison逐条小型ledger、summary和中文报告；
- 服务器大型产物路径、文件大小与SHA256清单。

首轮设计完成不代表工具已被正式纳入生产 QGIS 转换流水线。只有满足推广门禁并通过后续
独立实施决策，才能将Joern证据接入8,466条Processing或39,386条API全池driver。
