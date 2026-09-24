# DC-2A 规格：状态条件化 EOS logit bias（单变量，预注册）

日期：2026-09-24 冻结（跑前成文）
owner 裁定（2026-09-24）：DC-2 批准；**先 EOS-only（DC-2A），达标才开 DC-2B（Trie+EOS 组合）**；不做 λ 扫描、不加重复惩罚、不加 beam/长度惩罚；A1 不训、C2 冻结、RL 押后。
机制定位（DC-1 推出）：问题不是选项不合法，而是 **EOS 相对概率不足**——干预必须提升 EOS 相对质量，非继续扩掩码。

## 1. 干预定义（唯一变量）

对 A1 ep15 的 test-111 贪心生成，逐步施加：

```text
z_EOS' = z_EOS + β · 1[state = link-phase]
```

- **state = link-phase**：已生成文本中存在 ≥1 个**完整** L: unit（正则 `L:[a-zA-Z0-9_-]+>[a-zA-Z0-9_-]+` 完整匹配，增量解码计数）。依据：gold 111/111 行含 ≥1 link（P-先-L-后的格式结构中，进入 link 阶段 = 进入收尾段）；连通性变体（n_L ≥ n_P−1）仅覆盖 gold 77.5%，已否决。
- state 未触发时 z_EOS 原样（允许提前停止的路径不关闭）。
- **其余 logits 一律不动**；无 trie、无重复惩罚、无 beam/长度项。

## 2. β 标定规则（单值，禁扫；数据导出非拍脑袋）

β = C0 在 gold 终点处的健康 EOS 劣势中位数 + 0.5 nat：

```text
对 C0 做 111 gold 目标的 teacher-forced 前向；
在每个 gold 链的终止 EOS 位置计算 margin = max_{t≠EOS}(logit_t) − logit_EOS；
β = median(margin) + 0.5
```

依据：C0 停止健康，其 EOS margin 即"健康停止所需的优势"；给 A1 补足同一 margin，使其被 boost 状态下的 EOS 竞争力 ≈ C0 健康水平。标定值随 spec 执行记录，**不得二次调整**（一次定值；失败即如实归因"β=该值不足/机制无效"，不滑向搜索）。

## 3. 臂与判据（预注册）

- 臂：**A1 + DC-2A vs A1 自由（DC-0 锁定数字）**，test-111 全量，其余夹具 = DC-0 冻结生成配置；C0+DC-2A 不做（C0 非患者，组合归 DC-2B）。
- 冒烟门：8 行 A1+DC-2A（EOS 触发逻辑单测 + 生成行为人工核验），过门才跑全量。
- **达标 = 同时满足**：
  1. hit_cap Δ 点估计下降且 CI95 上界 < 0（显著减少）；
  2. repetition 率点估计下降；
  3. precision Δ ≥ −0.01（不下降）；
  4. recall Δ CI95 下界 > −0.05（防"憋住"：EOS↑/hit_cap↓ 但 recall 崩 = FAIL）；
  5. link F1 Δ CI95 下界 > −0.05（不显著恶化）。
- 防作弊对照：报告 A1+DC-2A 的停住率/长度相对 C0-free 的距离（是否趋近健康纪律，而非简单砍长度）。
- 判读：达标 → DC-2B（Trie+EOS 组合）立项；不达标 → 归因记录（"状态条件化 EOS 不足"），控制层路线整体重估，**不进入任何参数变体**。

## 4. 产物

`scripts/dc2a_eos_bias_gen.py`（含 C0 标定通道与 A1 生成通道）、`docs/reports/transfer_phase2/dc/dc2a_report.md`、标定记录、八行冒烟工件。
