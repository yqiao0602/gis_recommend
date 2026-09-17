# V2a-P2 Spec：Catalog-Constrained Structured Decoding（冻结）

日期：2026-09-17
状态：spec 冻结；门 A（环境）已完成；门 B（CPU 全量验证）已完成；**GPU 门（C/D）待批准**
前置：gold repeat audit（`79065a8`）确认重复为合法结构 → P2 严禁任何重复控制
实验定义（owner 2026-09-17 裁决原文）：**"限制模型只能生成合法的 QGIS 结构和 operator，但允许任意合法重复"**——不定位为 truncation 解决方案，定位为**结构化输出可靠性实验**

## 1. 约束面（恰好两层，不多不少）

```
JSON grammar（字段结构合法）
  + operator_id ∈ QGIS catalog（1,291 个，enum 精确成员）
  + 允许任意次数的元素重复（数组长度不限、同算子重复不限）
```

**明确排除**（双重证据禁止）：no-repeat / ngram blocking / 同算子惩罚 / 重复次数上限；**link/DAG 强约束**（第一版不做——link 是结构推理问题，与名称合法性混做会无法归因）。

**自由槽**：process_id、link source/target 值 = 自由字符串（不约束引用合法性——那是 link 约束的领地，本版不做）。

## 2. 实现（已验证可行）

- 引擎：**xgrammar 0.1.29**（离线轮子安装：xgrammar + pydantic 2.13.5 + pydantic-core 2.46.5 + annotated-types + typing-inspection；服务器环境变更记录在案，可 `pip uninstall` 回滚）
- 语法表达：**JSON Schema**（不走 EBNF——其方言不转义引号）；operator_id 用 `enum` 枚举全部 1,291 catalog 名
- 集成：自定义 `LogitsProcessor` 包 `GrammarMatcher`——每步 `fill_next_token_bitmask` + `apply_token_bitmask_inplace`；batch=1；greedy/512/EOS stop 与 C0 完全一致，**唯一差异 = 掩码存在**
- 功能验证（2026-09-17，CPU）：非法 token → -inf；合法实例全接受；非法算子名首 token 即拒

## 3. 实验对照

| | C0 | P2 |
|---|---|---|
| checkpoint | `v2a_a/adapter_v1`（冻结 A） | 同一个（不重训） |
| 解码 | free greedy/512/EOS | 同参数 + grammar/catalog 掩码 |
| 数据/打分 | Protocol v2 scorer + canon 列 | 同 |

## 4. 门（gate C/D 动 GPU 前必须全过）

**门 A（环境，✅ 已过）**：xgrammar 离线安装 + 功能掩码测试通过（本 spec §2）。

**门 B（CPU 全量验证，✅ 已过）**：
- B1：schema 含全 1,291 enum 时编译成功且耗时可接受
- B2（关键）：**全部 1,565 个 gold target（train 1,334 + dev 120 + test 111）逐一走 matcher，必须 100% 接受**——若 grammar 拒绝任何合法 gold，等于把模型约束到离开正确答案，实验作废前提
- B3：serialize 契约与 schema 字段序一致（processes→links，键序 process_id→operator_id）

**门 C（GPU smoke，8 行）**：约束下 parse_ok = 1.0（语法保证）、invalid_operator = 0（catalog 保证）、生成速度衰减可接受（记录 tokens/s 对比）、预测全文落盘。

**门 D（正式，dev+test 231 行）**：冻结协议评测链 + Protocol v2 打分，出 C0 vs P2 全表。

## 5. 预注册预期与判定（写死，不追高 F1）

1. **由构造保证的**：parse_ok ≈ 1.0、invalid_operator = 0——这两项不再是"结果"而是"约束的验证"
2. **真正的问题**：invalid↓ 是否转化为 **E2E Operator F1 ↑**（C0 dev 0.187 / test 0.131 基线）
3. **诚实记录面**：
   - conditional F1 若**下降** → 约束把"近失名称"逼到远处合法名，记为约束的伤害面
   - hit_cap 预期 ≈（语法不解决长链生成）；**若显著恶化**（语法把模型逼进死角出不来）→ 如实记失败
   - repetition 不变（合法重复被允许，本来就不该动）
4. **论文价值预设**（owner §7 原则）：即使只有"输出空间约束改善离散输出可靠性、长工作流生成仍是独立瓶颈"，也是干净结论

## 6. 结案条款

P2 完成后 V2a 路线收官判定：P0（正）+ ngram8（负）+ P1（负）+ repeat audit（定性）+ P2（?）→ benchmark v0.2.1 架构级对照（V1 vs V2a）。74 dup + W034030 型个案保留为 data_quality appendix，不动 Gold。
