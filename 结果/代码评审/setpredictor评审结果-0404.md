set predictor 在你这套系统里不是边缘模块，它会决定候选 token 集合、重复次数预算、长度提示，并且通过硬约束直接改写 transformer 解码 logits，所以它和 train_v4_6.py 是强耦合的两
  阶段。

  Findings

  1. [严重][联合] set predictor 的输出现在是硬约束，不是软提示；一旦漏掉真 token，就会直接禁止 transformer 生成它。_apply_constraints() 先把不在预算里的 token 全部打成 -inf，再叠加转移矩阵约束；只有在“所有预算
     都耗尽”时才整体放开约束。如果“预算集合”和“allowed_next”没有交集、同时还没到允许 END 的步数，就可能出现所有 token 都是 -inf。我本地验证过 F.log_softmax(all -inf) 会返回 nan，这不只是效果下降，而是有数值稳定
     性风险。src/gis_recommend/inference/infer_l3_candidates_v4.py:317 src/gis_recommend/inference/infer_l3_candidates_v4.py:330 src/gis_recommend/inference/infer_l3_candidates_v4.py:364 src/gis_recommend/
     inference/infer_l3_candidates_v4.py:451
  2. [严重][Set Predictor] train_set_predictor_v3.py 的训练/早停目标和线上 serving 方式仍然错位。训练阶段固定用 threshold=0.5 的 set_f1 做 early stopping，但线上默认是 Top-K 模式，top_k > 0 时 threshold 会被完
     全忽略。也就是说，你现在保存的 best checkpoint 不是按线上真实使用规则选出来的。结果文件也支持这一点：当前 best model 是按 0.5 阈值选出来的，但同一模型在测试集上 thr=0.7 的 F1 明显更高；而线上甚至不是
     threshold 模式。src/gis_recommend/training/train_set_predictor_v3.py:476 src/gis_recommend/training/train_set_predictor_v3.py:503 src/gis_recommend/models/set_predictor_v3.py:205 src/gis_recommend/models/
     set_predictor_v3.py:224 src/gis_recommend/inference/infer_l3_candidates_v4.py:282 结果/train_set_predictor结果/train_set_predictor_v3:125
  3. [高][Set Predictor/联合] count head 的定义会系统性放大 false positive。训练时 count loss 只在 binary_targets=1 的位置上计算，也就是说 count head 从来没有学过“这个 token 的 count 应该是 0”；但推理时，只要
     binary 分支把一个 token 选进来，不管它是真是假，count 都会被强行赋成 1/2/3 之一。于是 false positive 不只是“多选了一个 token”，而是会变成真实预算，进一步抬高 sum(counts.values())，影响长度提示和后续硬约
     束。src/gis_recommend/training/train_set_predictor_v3.py:179 src/gis_recommend/models/set_predictor_v3.py:230 src/gis_recommend/inference/infer_l3_candidates_v4.py:293 src/gis_recommend/inference/
     infer_l3_candidates_v4.py:397
  4. [高][Set Predictor/联合] 次数建模被截断在 3+，但推理时又把 3+ 还原成固定 3，这会低估重复 token 的真实预算。我本地统计当前数据集发现，114,401 个 workflow 里有 32,567 个至少包含一个“重复次数 >3”的 token，占
     28.47%，最大重复次数是 36。这意味着对重复算子比较多的工作流，set predictor 会先天性低估预算；在当前硬约束解码里，这种低估会导致某些本该继续出现的 token 被提前封死。src/gis_recommend/training/
     train_set_predictor_v3.py:123 src/gis_recommend/models/set_predictor_v3.py:230 src/gis_recommend/inference/infer_l3_candidates_v4.py:327 src/gis_recommend/inference/infer_l3_candidates_v4.py:459 outputs/
     pipeline/step8/labeled_workflows_l3_v4_cleaned.json
  5. [高][Set Predictor] set predictor 的 checkpoint 选择只看 set_f1，但它实际输出的是“集合 + 次数”，而次数在推理里又会直接参与预算递减和长度提示。代码里虽然打印了 count_acc、count_mae，但保存 best model 时完全
     不考虑这些指标。这意味着当前 best checkpoint 可能是“集合预测最好”的模型，却不是“预算控制最稳”的模型。src/gis_recommend/training/train_set_predictor_v3.py:485 src/gis_recommend/training/
     train_set_predictor_v3.py:503 src/gis_recommend/inference/infer_l3_candidates_v4.py:397 src/gis_recommend/inference/infer_l3_candidates_v4.py:459
  6. [中高][联合] train_v4_6.py 虽然已经把 transformer 的模型选择从 val_loss 改成了 AR-TokenAcc，但这个 AR-TokenAcc 仍然不是在线上真实推理栈里测出来的。训练里用的是不带 set predictor、不带 beam/diverse search、
     不带 transition hard mask 的 greedy decode；线上走的是 infer_l3_candidates_v4.py，里面有 set predictor 预算、长度提示、transition 约束和 diverse beam search。所以 V4.6 best_model.pth 比以前更合理了，但仍然
     只是“对第一阶段更对齐”，还不是“对两阶段联合推理最优”。src/gis_recommend/training/train_v4_6.py:310 src/gis_recommend/training/train_v4_2.py:795 src/gis_recommend/training/train_v4_2.py:813 src/
     gis_recommend/training/train_v4_2.py:748 src/gis_recommend/inference/infer_l3_candidates_v4.py:381 src/gis_recommend/inference/infer_l3_candidates_v4.py:391
  7. [中高][联合] 两阶段是分开训练的，而且各自有独立的 BERT/text encoder，没有共享表示，也没有一致性损失；但在推理时，set predictor 却用硬 mask 去约束 transformer。这种结构的典型问题是：只要两个模型对同一个输入
     的理解不一致，最终不是“协商”，而是由 set predictor 直接否决 transformer。当前实现里这是架构级的不稳定源。src/gis_recommend/models/set_predictor_v3.py:61 src/gis_recommend/models/transformer_model_v4.py:205
     src/gis_recommend/inference/infer_l3_candidates_v4.py:317

  补充说明

  - 我额外检查了一个容易怀疑的数据泄漏点：active_token_ids 虽然是在 split 之前从全量数据发现的，但当前这份数据里，train split 已经覆盖了全部 77 个 active tokens，所以这点现在不构成实际 token-support 泄漏。
  - 结果文件也和上面的代码审查是一致的：threshold 调整只能带来有限变化，瓶颈并不只是阈值，而是 set predictor 的判别力和它与解码器的耦合方式。结果/evaluate_system/V4.5+threshold-0.80.md:145

  结论
  是的，这些都在影响后续推理结果，而且联合阶段的问题通常比单阶段指标更伤。当前最重的问题不是“set predictor F1 不够高”这么简单，而是：

  - 它的训练目标和线上使用方式不一致
  - 它的 count 定义和真实解码预算不一致
  - 它在推理里是硬约束，错误会被放大
  - train_v4_6 选出来的 best transformer 也还没有对齐到“带 set predictor 的真实推理栈”



优化意见：

当前最该优先动的其实不是继续深挖 train_v4_6.py，而是把 set predictor 从“容易误伤第一阶段”的状态先拉回来。下面是我给你的修复优先级清单，按“最值”排序。

  P0 先做：不改大结构，先止损

  1. 把 set predictor 从硬约束改成软约束。
      - 当前最伤的是 src/gis_recommend/inference/infer_l3_candidates_v4.py:317 这里直接把不在预算里的 token 全打成 -inf。只要 set predictor 漏一个真 token，transformer 就永远没机会补回来。
      - 最值得的改法不是先重训，而是先把这层约束改成 logit bias。
      - 建议：
          - 预算内 token 加正偏置。
          - 预算外 token 不要 -inf，最多给小负偏置。
          - 如果约束后可选 token 集为空，立刻回退到“无 set predictor 约束”的 beam。
      - 这是最高 ROI，因为只改联合推理层，马上就能减少误杀和 nan 风险。src/gis_recommend/inference/infer_l3_candidates_v4.py:321 src/gis_recommend/inference/infer_l3_candidates_v4.py:364
  2. 暂时不要让 count head 决定硬预算。
      - 现在 count 预测是 {1,2,3+}，推理时又把 3+ 固定还原成 3；更关键的是，只要 binary 误选了一个 token，它就一定会被分配一个 >=1 的 count。src/gis_recommend/training/train_set_predictor_v3.py:123 src/
        gis_recommend/models/set_predictor_v3.py:230
      - 短期最值改法：
          - set predictor 只提供“候选 token 集合”或“长度提示”。
          - 不再逐 token 递减预算，不再靠 count 硬封 token。
      - 原因很直接：我统计过，当前数据里有 28.47% 的 workflow 至少包含一个重复次数 >3 的 token，当前 count 定义天然失真。
  3. 在线上 serving 模式确定前，不要继续用“训练按 threshold，线上按 Top-K”这套混搭。
      - 当前训练用 threshold=0.5 做 early stopping，src/gis_recommend/training/train_set_predictor_v3.py:476
      - 线上默认 Top-K，而 Top-K 会忽略 threshold。src/gis_recommend/models/set_predictor_v3.py:205 src/gis_recommend/inference/infer_l3_candidates_v4.py:282
      - 短期二选一：
          - 要么线上先切回 threshold 模式，用验证集挑阈值。
          - 要么训练验证立刻改成 Top-K 指标。
      - 不要继续维持现在这种“训练和使用不是同一规则”的状态。

  P1 下一轮必须做：重训 set predictor，但先对齐目标
  4. 在 src/gis_recommend/training/train_set_predictor_v3.py 里加入 Top-K 验证指标，并按 serving 指标保存 best model。

  - 如果线上继续用 Top-K，那验证阶段就应该按每个样本的 K 来算 set_f1，并用这个指标 early stop。
  - K 要和推理侧一致，最好直接复用 task type 的 expected_length 逻辑，而不是重新拍脑袋设定。
  - 这一步的收益会比继续调 threshold 大得多。

  5. checkpoint 选择不要只看 set_f1，至少要把 count 质量纳入副指标。
      - 当前 best checkpoint 完全按 set_f1 保存，src/gis_recommend/training/train_set_predictor_v3.py:503
      - 但线上实际用到了 count 去影响预算和长度，所以只看集合对不对是不够的。
      - 建议保存时用：
          - 主指标：serving 模式下的 set F1
          - 副指标：count_mae 或长度误差
      - 现在训练 loader 只是 shuffle=True，没有像 V4.5/V4.6 那样做按 task type 的平衡采样。src/gis_recommend/training/train_set_predictor_v3.py:338
      - 由于它本质上也是“自然语言 + task_type -> token set”，任务类型分布不均会直接影响它对少数类的召回和精度。
      - 这是中等成本、高概率收益的改动。
  7. BCE 的 pos_weight 不要再用单一全局标量，改成按 token 的权重。
      - 当前 compute_pos_weight() 只算了一个全局 absent/present ratio。src/gis_recommend/training/train_set_predictor_v3.py:273
      - 但 token 频率显然高度不均，一把尺子压所有 token，稀有 token 会继续学不好。
      - 这个不是最优先，但在 set predictor 精度上通常会有实际收益。

  P2 结构改造：值大，但放在前两轮之后
  8. 重做 count head，不要继续用 {1,2,3+} 直接驱动预算。

  - 两种更稳的方案：
      - 方案 A：把 count 改成 {0,1,2,3,4+} 或更细的桶。
      - 方案 B：把 count 从“硬预算”降级成“长度提示”，真正的 token 选择仍由集合分支和 transformer 决定。
  - 如果只看收益/风险比，我更推荐先走方案 B，便宜且稳。

  9. 不要急着做端到端 joint training，先做 joint selection。
      - 当前 train_v4_6.py 选 transformer best model 用的是 greedy AR 指标，不带 set predictor。src/gis_recommend/training/train_v4_6.py:310
      - 线上真实推理却带了 set predictor、transition 约束和 beam search。src/gis_recommend/inference/infer_l3_candidates_v4.py:381
      - 更值的改法不是马上 joint train，而是：
          - 每隔若干 epoch，用固定验证子集跑一次“真实联合推理”
          - 按联合 Set F1 / Token Accuracy / Length Ratio 选 transformer checkpoint
      - 这样成本远低于联合训练，但能显著减少“两阶段各自最优、拼起来不优”的问题。
  10. 让两阶段至少共享“同一种文本理解”或做蒸馏。

  - 现在两边各有一套独立 BERT，没有共享，也没有一致性约束。src/gis_recommend/models/set_predictor_v3.py:61 src/gis_recommend/models/transformer_model_v4.py:205
  - 这会导致 set predictor 和 transformer 对同一条自然语言的理解不一致，最后由 set predictor 在推理时直接 veto transformer。
  - 这个方向值得做，但优先级低于前面几项。

  最值实施顺序

  1. 先改联合推理：硬约束改软约束，count 不再当硬预算。
  2. 再改 train_set_predictor_v3.py：验证/early stop 切到与线上一致的 serving 指标。
  3. 然后重训 set predictor，并用新的联合推理做端到端评估。
  4. 最后再考虑 count head 重构和 transformer 的联合 checkpoint 选择。

  一句话判断
  当前最值的不是“把 set predictor 训得更复杂”，而是先阻止它在联合推理里“错一次、杀一片”。等推理耦合方式改对，再重训 train_set_predictor_v3.py，收益会比现在直接继续调参高很多。



实施方案建议：

下面给你一份“按投入产出比排序”的可执行改造方案，专门针对 src/gis_recommend/training/train_set_predictor_v3.py、src/gis_recommend/models/set_predictor_v3.py 和 src/gis_recommend/inference/
  infer_l3_candidates_v4.py。

  P0 最值改法：先止损联合推理

  1. 在 src/gis_recommend/inference/infer_l3_candidates_v4.py:270 把 _predict_token_set() 改成“返回 soft prior”，不要再直接返回硬预算。
     建议新接口叫 _predict_token_prior()，返回：
      - presence_probs: Dict[token_id, float]
      - selected_tokens: Set[int]
      - predicted_counts: Dict[token_id, int]
        这样后面可以同时支持 off / soft / hard 三种模式，不必一开始就删旧逻辑。
  2. 在 src/gis_recommend/models/set_predictor_v3.py:190 新增 predict_token_scores()，不要只暴露 predict_token_counts()。
     最小可行输出：
      - 每个 token 的 p_present
      - 每个 token 的 count_probs
      - 一个可选的 topk_indices
        predict_token_counts() 可以保留，用 predict_token_scores() 包一层兼容旧调用。
  3. 在 src/gis_recommend/inference/infer_l3_candidates_v4.py:312 把硬 mask 改成 soft bias。
     现在的问题是预算外 token 直接 -inf，漏一个真 token 就永远回不来。
     建议改成：
      - prior 内 token：+1.0 ~ +2.0 的 logit bonus
      - prior 外 token：-0.3 ~ -1.0 的轻惩罚
      - END 始终保留
      - transition mask 仍可保留，但也要加 fallback
        这样 set predictor 仍然能“引导” transformer，但不会一票否决。
  4. 在 src/gis_recommend/inference/infer_l3_candidates_v4.py:321 加数值安全回退。
     在 _apply_constraints() 末尾检查：
      - 如果某个样本 torch.isfinite(logits[b]).sum() == 0
      - 立刻回退到“只保留 special token mask，不加 set predictor 约束”
        否则 log_softmax(all -inf) 会直接出 nan。
  5. 在 src/gis_recommend/inference/infer_l3_candidates_v4.py:395 和 src/gis_recommend/inference/infer_l3_candidates_v4.py:519 先取消“set predictor 改写 expected_length”。
     当前 self.expected_length = max(set_pred_length, self.expected_length) 会把 count 误差直接放大成长度偏差。
     P0 阶段建议：
      - expected_length 只由 task type length stats 决定
      - set predictor 只参与 token prior，不参与长度覆盖
        这是最值的切法，因为它马上能减少长度漂移。
  6. 在 src/gis_recommend/inference/infer_l3_candidates_v4.py:459 和 src/gis_recommend/inference/infer_l3_candidates_v4.py:569 暂时不要再按 count 递减硬预算。
     P0 阶段直接把 budget decrement 去掉，或者仅用于 debug 统计，不用于屏蔽 token。
     理由很简单：当前 count 定义是 {1,2,3+}，它还不配拿来做硬预算。

  P1 第二步：重训 set predictor，但先把目标对齐线上
  7. 在 src/gis_recommend/training/train_set_predictor_v3.py:197 新增 compute_metrics_topk()，不要再只用 threshold=0.5 的 compute_metrics()。
    这个新函数要按线上规则评估：

  - 如果线上决定继续用 Top-K
  - 验证集就按每个样本的 K 取 top-k token，再算 set F1
    K 建议直接复用 task type 的中位长度策略，和推理保持一致。

  8. 在 src/gis_recommend/training/train_set_predictor_v3.py:476 改 early stopping 和 best checkpoint 逻辑。
     当前是：
      - threshold=0.5
      - metrics['set_f1']
        建议改成：
      - 主指标：topk_set_f1
      - 副指标：count_mae 或 avg_pred_size 偏差
        保存 checkpoint 时把 selection_mode='topk' 和 k_strategy='task_type_median_cap15' 一起写进 metadata。
  9. 在 src/gis_recommend/training/train_set_predictor_v3.py:338 给训练 loader 加 task-type balancing。
     方式和 V4.5/V4.6 类似，按 task type 做 WeightedRandomSampler。
     这一步非常值，因为 set predictor 和 transformer 本质上都在做“文本到结构”的预测，少数 task type 不平衡会直接拖低线上表现。
  10. 在 src/gis_recommend/training/train_set_predictor_v3.py:273 把 pos_weight 从全局标量改成按 token 的向量。

     当前所有 token 共用一个 absent/present ratio，这对高频 token 和低频 token 明显不公平。
     改法：

  - 统计 train split 上每个 active token 的 present 次数
  - 生成 pos_weight_vec[i] = n_absent_i / n_present_i
  - 做一个上下限裁剪，比如 clamp(1, 20)
  - TwoStageLoss 接收向量而不是标量

  11. 先不要大动 count head，但把它从“主驱动”降成“辅指标”。

     当前 src/gis_recommend/training/train_set_predictor_v3.py:123 的 count bucket 是 {1,2,3+}，短期内先接受这个定义，但不要再让它决定硬预算。
     P1 目标是：

  - binary/presence 预测先更准
  - count 先只做辅助长度提示或 debug 指标

  P2 第三步：把两阶段的“选模”也对齐
  12. 不要只按 src/gis_recommend/training/train_v4_6.py 的 greedy AR-TokenAcc 选线上模型。
    这已经比旧版好，但它还是“第一阶段单独最优”，不是“两阶段联合最优”。
    最值做法不是马上 joint training，而是做 joint selection。

  13. 新增一个轻量验证脚本，建议单独建：

  - scripts/eval_joint_val.py
  - 输入：transformer checkpoint、set predictor checkpoint、prior mode
  - 流程：直接调用 src/gis_recommend/inference/infer_l3_candidates_v4.py 的真实推理链
  - 输出：Set F1 / Token Accuracy / Length Ratio
    用它在验证集小子集上评估多个 transformer checkpoint，再决定真正上线哪个。

  14. 在 scripts/evaluate_system.py 增加一个开关，建议叫：

  - --set-prior-mode off|soft|hard
    这样你能直接做三组 A/B：
  - off: 不用 set predictor
  - soft: 软先验
  - hard: 旧硬约束
    这一步很关键，因为它能直接验证“问题到底在模型，还是在耦合方式”。

  我建议的实际实施顺序

  1. 先改 src/gis_recommend/inference/infer_l3_candidates_v4.py 和 src/gis_recommend/models/set_predictor_v3.py，把 hard budget 改成 soft prior，并加 fallback。
  2. 然后改 scripts/evaluate_system.py，做 off/soft/hard 三组对比，先看“只改联合推理”能带来多少提升。
  3. 再改 src/gis_recommend/training/train_set_predictor_v3.py，把验证目标切到 Top-K serving-aligned 指标，并加入 balancing + per-token pos_weight。
  4. 重训 set predictor。
  5. 最后再用联合验证脚本，在多个 V4.6 checkpoint 上选出真正上线版本。

  验收标准

  - soft 模式下，端到端 Set F1 应该至少不低于 off，并显著优于 hard。
  - 不应再出现约束后全 -inf 或 nan 的数值问题。
  - set predictor 训练日志里，主监控指标应变成 serving-aligned 的 TopK-SetF1，不再是单纯 threshold=0.5 F1。
  - 联合评估时，Length Ratio 不应再被 set predictor count 误差明显拉偏。

  暂时不要优先做

  - 不要一上来就做 transformer + set predictor 的端到端联合训练。
  - 不要继续在旧的 hard mask 结构上细调 threshold。
  - 不要继续让 count head 驱动硬预算，至少在它重构之前不要这么做。