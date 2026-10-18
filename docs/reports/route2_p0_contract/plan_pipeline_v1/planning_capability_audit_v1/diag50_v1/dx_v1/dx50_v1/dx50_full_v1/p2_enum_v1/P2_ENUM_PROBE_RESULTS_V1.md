# P1 Enum 展开探针结果 V1

对照=A1 v0_5 臂（冻结）；实验=同提示+卡面追加 choice 值。n=3，只做逐对描述。

| 步骤 | 对照 | 实验 | 对照选择 | 实验选择 | 对照 tokens | 实验 tokens |
|---|---|---|---|---|---|---|
| PCA2-T-009#S4 | ABST | POS | - | otb:trainvectorclassifier | 1196(END_MARK) | 1511(EOS) |
| PCA2-T-009#S6 | POS | NODEC | otb:trainvectorclassifier | - | 1196(EOS) | 1511(EOS) |
| PCA2-T-056#S6 | POS | POS | saga:supervisedclassificationforrasters | saga:supervisedclassificationforrasters | 1704(EOS) | 1511(EOS) |

## 枚举值引用（决策文本中出现的 dt/rf 等）

- PCA2-T-009#S4：对照 ['decision tree', 'random forest'] ｜ 实验 ['classifier.rf', 'decision tree', 'random forest']
- PCA2-T-009#S6：对照 无 ｜ 实验 无
- PCA2-T-056#S6：对照 ['random forest'] ｜ 实验 ['random forest']