# V2a Gold 重复算子审计（read-only，owner 裁决 b）

日期：2026-09-17
状态：纯 CPU 审计完成，未修改任何数据/benchmark/模型
脚本：`scripts/audit_v2a_gold_repeats.py`；明细：`docs/reports/v2a_results/gold_repeat_audit.json`
背景：三轮干预（ngram8 净负 / EOS λ=20 净负 / canonical +0.03）后，owner 裁决先回答"重复在 GIS 语义上是什么"再决定 P2

## 1. 主表一：连续重复长度分布（train 1,334 行，822 个 run）

结构判定（gold 契约无参数字段，用 DAG 角色代理）：**fanout=合法**（成员有不同的父/子邻域=独立实例，或扇出汇聚到单点）；**chain=自喂链**（run 成员彼此相连，算子吃自己输出）；**dup=疑似伪重复**（邻域完全相同）。

| 连续长度 | run 数 | 合法(fanout) | 疑似(chain/dup) |
|---:|---:|---:|---:|
| 2 | 563 | 219 | 344 |
| 3 | 151 | 42 | 109 |
| 4–5 | 70 | 12 | 58 |
| 6–8 | 24 | 3 | 21 |
| 9–16 | 14 | 1 | 13 |

**长度越长越疑似**：9-16 连的 14 个 run 里只有 1 个是纯扇出。

## 2. 主表二：结构类型分布（train）

| 类型 | 数量 | 占比 | 语义判读 |
|---|---:|---:|---|
| fanout_distinct（不同 DAG 位置/邻域） | 257 | 31% | **合法**：多实例并行（如多图层分别处理） |
| fanout_converge（扇出→单点汇聚） | 20 | 2% | **合法**：经典 fan-in（如 16 buffer→merge） |
| **chain 纯自喂链**（每对相邻都相连） | 400 | 49% | **见 §3：多数是合法习语，部分疑似序列化产物** |
| chain 部分（部分相邻相连） | 71 | 9% | 混合体，需个案看 |
| dup_same_nbhd（邻域完全相同） | 74 | 9% | **疑似 extraction artifact** |
| dup_isolated（完全无边） | 0 | 0% | — |

## 3. 自喂链的算子拆解（关键发现）

纯自喂链 400 个，头部算子：

| 算子 | 纯链数 | GIS 语义判读 |
|---|---:|---|
| native:fieldcalculator | 101 | **合法习语**：逐字段顺序构建（QGIS 脚本常见写法） |
| native:buffer | 24 | 大概率**合法**：多环缓冲（100m/200m/… 依次套） |
| native:intersection | 20 | 合法偏多：多图层依次求交 |
| native:joinattributestable | 18 | **合法习语**：逐表顺序连接属性 |
| native:snapgeometries / extractbyexpression / zonalstatisticsfb | 44 | 迭代精化/分区统计，合法习语为主 |
| gdal:rastercalculator | 13(+12 部分) | 多步栅格代数，合法为主 |

**结论：chain ≠ artifact。** 自喂链的主体（fieldcalculator/join/buffer 环）是**真实 GIS 脚本的书写习语**——它们在 QGIS 里确实被串联使用。

## 4. 三个 headline 案例核验

| wid | run | 结构 | 判读 |
|---|---|---|---|
| W051622（train max） | 16× gdal:rastercalculator | 仅 3 条内部链，但全图 24 proc/93 link 密集互连 | **合法**：MOPST 旅游压力分析的多步栅格代数网络，非跑马 |
| W067268（dev max） | 12× native:fieldcalculator | 10 条内部链（近纯链） | **合法习语**：BS 5228 噪声预测逐字段构建 |
| W034030（test max） | 15× qgis:distancematrix | 14 条内部链（纯链） | **最可疑的一个**：鹦鹉逐年移动分析，逐年距离矩阵按理应并行扇出（各自→汇总），串成链更像序列化习惯/artifact |

## 5. 审计结论

1. **Gold 重复以合法结构为主**：fanout 34% + 合法习语链（fieldcalculator/join/buffer 环等，约占 chain 的 70%+）→ **结构合法占比约 2/3 以上**。真正疑似 artifact 的只有 dup_same_nbhd 74 个（9%）+ 少数长链个案（如 W034030 型）。
2. **ngram8 失败由此完全解释**：gold 要求模型学会"同算子长串重复是正常模式"，而 ngram/penalty 类机制在 token 层禁止的恰是这个模式。这不是调参能解决的——是**表示与机制的 structural conflict**。
3. **EOS λ=20 失败同理得到旁证**：gold 中"重复后继续"与"完成后停止"都高频存在，单 token 加权无法只强化后者。
4. dev/test 分布与 train 一致（37/120、44/111 行含 run），评测口径未被 train 特异性污染。

## 6. 对 P2 的直接约束（若立项）

- **禁止任何 repetition/ngram 类约束**（本审计 + report_v4 双重否定）
- P2 只能做**语法层约束**：JSON grammar + operator_id catalog 合法性 + process_id/link schema——它治理 invalid operator（0.39→可趋 0）而不触碰重复
- 预期收益上界 = canonicalization 已量化的名称修复空间（+0.03~0.04）加语法兜底，**不解决 truncation**（repetition_rate 0.39 里合法部分是 gold 要求的）

## 7. 数据侧残余（记录，不动手）

dup_same_nbhd 74 个 run + W034030 型个别长链 = 约 10% 疑似 artifact，属可修数据噪声；若未来重冻 A（数据侧修复路线），这是唯一名单来源。本轮不修。
