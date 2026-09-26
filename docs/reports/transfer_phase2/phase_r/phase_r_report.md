# Phase R 报告：v2a_A L1 管线预演 —— CLOSED-FAIL（基础设施/evaluator 失败）

日期：2026-09-24（2026-09-26 owner 定性补记）
规格：`docs/plans/transfer_phase2_stage2_prereg_v1.md` §0/§5
**Owner 官方处置（2026-09-26）：Phase R = CLOSED-FAIL（Infrastructure / evaluator failure），严格区别于 "Stage 2 = FAIL"。** 训练链五项 PASS；evaluator 链 FAIL 导致选点未验证。`opF1=-1.0 / n=0` 是 OOM sentinel，统计上不是模型观测值——禁止产生任何模型效果结论（不得写 C0R "效果不好"，也不得与 C0 比较好坏）。不重训、不改配方。

## 冻结输入身份

- C0 recipe clone：`C0R_rehearsal.yaml` SHA256 `6737b86293b1f24de0c982b13a94c3739ab119cf7f2f9353a76e2017f742c6a1`
- Base：`/home/qy/models/Qwen3.5/Qwen3.5-9B-Base`
- QGIS train 1,334 SHA256 `1199adb60ad6bf9eef51449fa83e685bc99829276c2a8f18d6ea7d9d02d4a538`
- Dev-120 SHA256 `8510c1f96b3e9bfaaf16e1d5cc8afeb0a0a9f273f9c7a9bc3ecaf8381aa8a2ce`
- Test-111 SHA256 `8827b72f86e2a21e7925466bcdce8f17e60e6220ee96a3334d1002d1a428b8c6`
- Run ledger SHA256 `7124ad1de00f11f2c1c7cfcaf8ab6c50a0f3dabb91989e8733f6ad7ee54be59a`
- Preflight SHA256 `9cf234f5747eac8ea9a2e70a9cecbf210d7848b046b3c84f470e76920f30bbb6`

## 实际结果（run_ledger 与服务器实测）

- 3/3 训练 epochs 完成；epoch 1/2/3 checkpoint 均落盘；4,002 example exposures / 1,165,662 tokens；prompt truncation=0、target truncation=0。
- 三次 dev-120 evaluator 子进程均 OOM：尝试申请 7.01 GiB，而共享 GPU 仅余 6.92 GiB。训练器将三次 eval 都记录为 sentinel `operator_set_f1=-1.0, n=0, parse_failure_rate=1.0`。
- `best_checkpoint=None`；不可用于任何 checkpoint selection / 效果分析。
- CUDA OOM 的共享占用：C0R 训练进程约 7.5 GiB + Ollama 两进程约 7.6 GiB + yyt/SAM3 约 5.6 GiB。训练进程退出后 GPU 计算列表无 C0R；剩余任务属于他方，不触碰。

## 验收表（严格照 Phase R 性质）

| 环节 | 状态 | 证据 |
|---|---|---|
| 数据 SHA / preflight | PASS | preflight_report.json 三 split SHA 与 P0 契约一致 |
| 数据装载 / loss / 训练步 | PASS | 3 epochs 完整完成，ledger 记录 1,165,662 tokens |
| 完整目标 EOS 可见性 / 截断核验 | PASS | target truncation 0、prompt truncation 0 |
| Checkpoint 保存 | PASS | qgis_sft_ep1/2/3 均在 |
| dev evaluator / checkpoint selection | **FAIL** | 三次 OOM；best=None；无有效 dev 数字 |
| Phase R 总判定 | **FAIL / 未闭环** | spec 要求训练管线 + scorer 三面接口能完整跑通；选点子流程未验证 |

## 解释纪律与后续

- dev `-1.0` 是 OOM sentinel，不是模型得分；不得作为效果数字引用，也不得写"模型表现差"。
- 本次是预演管线验证，不是 Stage 2 效果实验；所有潜在效果信息封存，不进入正式结论。
- 不按当前日志重试，不改 Phase R 配方，不重训；C0R 进程已退出。
- 最小技术风险定位：训练进程持有 4-bit Base + LoRA 时，`train.py` 再启动独立 `evaluate_dev.py` 重载第二份 4-bit Base；共享 GPU 可用 6.92 GiB < evaluator allocator warmup 请求 7.01 GiB。**这是 evaluator 资源生命周期问题，不是 Stage 2 训练配方问题。**
- **恢复条件（owner 预注册，2026-09-26）**：若需恢复，注册为 **"Phase R evaluator-repair rerun"**，不是新实验。只允许修复"训练完成 → checkpoint 保留 → evaluator 串行执行/释放训练显存 → dev-120 scorer → checkpoint selection"这一链路。**禁止顺便改动**：LR / batch / LoRA / epoch / 数据 / prompt / target / EOS / loss。越界即从"管线修复"变成新实验。
- **排程（owner 裁定）**：当前不立即修 R。顺序 = 等并行线 Base zero-shot → Stage-1 Gate builder → A/B Gate 判定 → 届时决定是否进入 Phase F（及是否需要 R 的 evaluator-repair rerun）。
- checkpoint 不作为效果工件同步是正确处置：R 目的只是验证管线，selection 未完成；有价值工件 = recipe + preflight + ledger + log + failure report。

工件目录：本目录下 `C0R_rehearsal.yaml`、`preflight_report.json`、`run_ledger.json`、`l1_rehearsal.log`；checkpoint 位于服务器 `/home/qy/gee_llm_smoke/route2_l1_rehearsal/`，尚未同步（Phase R 不作为效果工件提交）。
