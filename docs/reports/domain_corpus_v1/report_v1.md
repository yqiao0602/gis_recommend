# domain_corpus_v1 构建报告（v1 冻结）

日期：2026-09-14（服务器构建 16.2 分钟，attempt 2）
性质：corpus construction；零训练；`/home/yll` 只读；未修改任何 authority/评测/checkpoint
构建脚本：`scripts/build_domain_corpus_v1.py`；规则 spec：`docs/plans/domain_corpus_v1_spec.md`（v1 已冻结）

## 输入与产物

输入（SHA 见 manifest）：
- Asset Miner v2 normalized ledger（47,852 唯一 source SHA，服务器副本哈希 `a13ce1a2…` 与仓库镜像一致）
- 排除组：237 SHA（benchmark candidate_supply 全部 146 个非空 source SHA 的保守超集 + paper_v1 val/test 95 行来源）
- 泄漏集：3,709 个任务语义 6-gram（benchmark dev/final/refusal 132 + paper_v1 val/test 95 文本；见下方"泄漏集修正"）
- taxonomy_128_v1.json（SHA `45860335…` 与权威一致）

产物（服务器 `/home/qy/gee_llm_smoke/domain_corpus_v1/`，本目录镜像 manifest/ledger/budget/recipe；大型池 JSONL 留服务器，hash ledger 入库）：

| 池 | docs | bytes | wordpiece census |
|---|---:|---:|---:|
| D3 代码（清洗/去重/泄漏过滤后） | 43,809 | 651.2 MB | 174,676,396 |
| D4 docstring（英文池） | 112,196 | 21.2 MB | 5,714,676 |
| D4 README（英文池） | 1,276 | 3.0 MB | 886,764 |
| D1 taxonomy 锚点 | 128 | 16 KB | 3,447 |
| 合计 | — | — | 181,281,283 WP |

## 管线过滤账（47,852 → 43,809 入池 D3，保留 91.6%）

- SHA 排除组：55 剔除
- 自动生成检测：3,914 剔除
- 6-gram 泄漏：**46 剔除**（真实任务语义命中）
- 内容级精确去重：1；过小（<50B）：2；L3 结构命中：0
- docstring 提取（AST）：143,964 条 → 英文池准入 112,196；README 关联：1,285 发现 → 1,276 英文池

## 断言电池（全过）

excluded_sha_not_in_corpus ✓ | l3_codes_absent_in_d3_d4 ✓ | d1_codes_within_whitelist (128/128) ✓ | no_task_to_l3_pair_pattern ✓ | six_gram_zero_on_final ✓ | d5_train_texts_absent_by_construction（结构性保证：本构建不读 paper_v1 train 文本）✓ | no_frozen_artifact_modified ✓

## 事故与修复：泄漏集 GPL 样板误杀（attempt 1 → 2）

**事故**：paper_v1 **test split 有 1 行**（`qgis_pool_v1_qgis_api_pattern_1e554a92e0bd809c52cce173_v1`，api_pattern 池）的 task_text 本身是 GPL-3 许可证头（200 字符；该线当年提取任务文本时把许可证头当作 docstring）→ 泄漏集因此含 30 个 GPL 样板 6-gram → attempt 1 误杀 **15,340 个 GPL 授权 QGIS 源文件**（过滤率异常 40%）。

**修复**：从泄漏集剔除五族标准许可证样板 gram（GPL-2/GPL-3/MIT/BSD/Apache 标准序言；公共标准文本、零任务语义，任务语义保护不受损）：3,739 → 3,709 gram。attempt 2 泄漏命中降至 46（真实量级）。attempt 1 产物存档 `attempt1_gpl_gram_bug/`（含原 manifest 与 1.78MB 命中清单，未删除）。

**数据质量注记（paper_v1 冻结 manifest 不动，仅记录）**：paper_v1 test 46 行中 1 行任务文本为许可证文本（任务语义为空）——影响 46 行 test 诊断与未来 test 评测（1/46 噪声），也解释了本次误杀的来源。

## 冻结 recipe（owner 拍板 2026-09-14，M1-R2 §10 已同步冻结）

- D3：**60% 降采样**（seed 20260914，kept 26,285 / dropped 17,524，SHA 清单在服务器 `recipe_freeze_v1.json`）
- D4：**4× oversampling**（epoch/sample 级、同 seed，可复现；不复制文件）
- D1：**1× 原始保留**（锚点，非训练量来源；不做大规模过采样）
- **双口径纪律**：wordpiece census（181.3M）只描述 corpus 规模；**byte-level training budget = 487.5M byte-tokens**（D3 390.7MB + D4 96.8MB + D1 16KB）才是 DAPT 预算——steps/epoch/lr/GPU 时间/checkpoint 解释一律用 byte 口径
- **Exposure（byte 口径）**：D3 80.15% / D4 19.85% / D1 0.003%

## 复现

```bash
# 服务器（/home/qy/gee_llm_smoke）
python build_domain_corpus_v1.py --ledger qgis_asset_normalized_v1.jsonl \
  --exclusion outputs_tmp_domain_corpus_paths_v1.excl.json \
  --grams outputs_tmp_domain_corpus_paths_v1.grams.json \
  --taxonomy taxonomy_128_v1.json --out-dir domain_corpus_v1
```
（grams 文件为 GPL 修正版；排除组与 gram 集构建脚本逻辑见 spec §5-6）
