# A1 配对分析 V1（机械层：三分决策 + 配对转移）

配对数：158（受影响步全集；135 个不受影响步按构造排除）

| 臂 | 正选 | 显式弃权 | 无判定 | n |
|---|---|---|---|---|
| 对照 v0_4 | 24 (15.2%) | 68 (43.0%) | 66 (41.8%) | 158 |
| 实验 v0_5 | 31 (19.6%) | 59 (37.3%) | 67 (42.4%) | 158 |

## 配对转移（预注册四类 + same/shift）

- ABST->ABST(same): 46
- NODEC->NODEC(same): 45
- ABST->NODEC(shift): 17
- POS->POS: 17
- OTHER->POS(gain): 14
- NODEC->ABST(shift): 11
- POS->OTHER(loss): 7
- NODEC->OOC(shift): 1

选择集合变化步数：24；实验臂选中 provenance_unverified 算子的步数：0

## 按任务分层

- PCA2-T-001: {'NODEC->NODEC(same)': 1, 'OTHER->POS(gain)': 1, 'ABST->NODEC(shift)': 1, 'NODEC->ABST(shift)': 1, 'POS->OTHER(loss)': 1}
- PCA2-T-003: {'NODEC->NODEC(same)': 2, 'OTHER->POS(gain)': 1, 'POS->POS': 1, 'ABST->ABST(same)': 1}
- PCA2-T-005: {'ABST->ABST(same)': 3, 'NODEC->ABST(shift)': 1, 'POS->OTHER(loss)': 1}
- PCA2-T-006: {'ABST->ABST(same)': 1, 'POS->POS': 1}
- PCA2-T-009: {'NODEC->NODEC(same)': 4, 'OTHER->POS(gain)': 2, 'ABST->ABST(same)': 2}
- PCA2-T-012: {'NODEC->NODEC(same)': 1, 'ABST->ABST(same)': 2, 'NODEC->ABST(shift)': 1}
- PCA2-T-013: {'POS->POS': 2, 'NODEC->NODEC(same)': 1}
- PCA2-T-021: {'ABST->ABST(same)': 3, 'ABST->NODEC(shift)': 1, 'NODEC->NODEC(same)': 1}
- PCA2-T-022: {'ABST->ABST(same)': 1, 'OTHER->POS(gain)': 1}
- PCA2-T-023: {'ABST->ABST(same)': 1}
- PCA2-T-024: {'ABST->ABST(same)': 2, 'NODEC->NODEC(same)': 2}
- PCA2-T-025: {'ABST->ABST(same)': 1, 'POS->POS': 1, 'OTHER->POS(gain)': 2}
- PCA2-T-026: {'POS->OTHER(loss)': 1}
- PCA2-T-027: {'POS->POS': 1, 'ABST->ABST(same)': 1}
- PCA2-T-029: {'NODEC->NODEC(same)': 1}
- PCA2-T-030: {'ABST->ABST(same)': 2}
- PCA2-T-032: {'OTHER->POS(gain)': 1, 'NODEC->NODEC(same)': 1}
- PCA2-T-033: {'OTHER->POS(gain)': 1, 'NODEC->NODEC(same)': 2, 'POS->POS': 1}
- PCA2-T-037: {'ABST->ABST(same)': 1}
- PCA2-T-042: {'ABST->NODEC(shift)': 1, 'ABST->ABST(same)': 1}
- PCA2-T-046: {'POS->OTHER(loss)': 1, 'POS->POS': 1}
- PCA2-T-048: {'NODEC->NODEC(same)': 2, 'POS->POS': 1}
- PCA2-T-052: {'ABST->NODEC(shift)': 1, 'NODEC->NODEC(same)': 1, 'ABST->ABST(same)': 1}
- PCA2-T-053: {'NODEC->NODEC(same)': 1}
- PCA2-T-056: {'NODEC->ABST(shift)': 2, 'OTHER->POS(gain)': 2, 'ABST->NODEC(shift)': 1, 'NODEC->NODEC(same)': 1}
- PCA2-T-057: {'ABST->ABST(same)': 1, 'POS->POS': 1, 'NODEC->NODEC(same)': 1, 'OTHER->POS(gain)': 1}
- PCA2-T-058: {'ABST->ABST(same)': 1}
- PCA2-T-059: {'ABST->ABST(same)': 2, 'NODEC->NODEC(same)': 1}
- PCA2-T-060: {'ABST->NODEC(shift)': 1, 'NODEC->NODEC(same)': 1, 'ABST->ABST(same)': 1}
- PCA2-T-062: {'ABST->ABST(same)': 3, 'NODEC->NODEC(same)': 1, 'ABST->NODEC(shift)': 1}
- PCA2-T-068: {'ABST->ABST(same)': 2, 'NODEC->ABST(shift)': 1, 'NODEC->NODEC(same)': 1, 'OTHER->POS(gain)': 1}
- PCA2-T-069: {'NODEC->NODEC(same)': 1}
- PCA2-T-070: {'OTHER->POS(gain)': 1, 'NODEC->NODEC(same)': 2}
- PCA2-T-071: {'ABST->ABST(same)': 1, 'NODEC->NODEC(same)': 1}
- PCA2-T-072: {'ABST->ABST(same)': 1}
- PCA2-T-073: {'ABST->NODEC(shift)': 1}
- PCA2-T-079: {'POS->POS': 1, 'ABST->NODEC(shift)': 1, 'ABST->ABST(same)': 1, 'NODEC->ABST(shift)': 1}
- PCA2-T-080: {'ABST->NODEC(shift)': 1, 'NODEC->NODEC(same)': 2, 'POS->POS': 1}
- PCA2-T-081: {'ABST->ABST(same)': 1, 'NODEC->ABST(shift)': 1}
- PCA2-T-083: {'NODEC->NODEC(same)': 2, 'ABST->NODEC(shift)': 1, 'POS->POS': 1}
- PCA2-T-084: {'NODEC->ABST(shift)': 2, 'NODEC->NODEC(same)': 1, 'ABST->NODEC(shift)': 1, 'POS->POS': 1}
- PCA2-T-086: {'POS->POS': 1, 'ABST->NODEC(shift)': 2}
- PCA2-T-087: {'ABST->ABST(same)': 2, 'NODEC->NODEC(same)': 3}
- PCA2-T-089: {'ABST->ABST(same)': 3, 'POS->OTHER(loss)': 1, 'ABST->NODEC(shift)': 1, 'POS->POS': 1, 'NODEC->NODEC(same)': 1}
- PCA2-T-090: {'NODEC->NODEC(same)': 2, 'NODEC->OOC(shift)': 1}
- PCA2-T-092: {'ABST->ABST(same)': 1, 'POS->OTHER(loss)': 1, 'ABST->NODEC(shift)': 1, 'NODEC->NODEC(same)': 2, 'POS->POS': 1, 'NODEC->ABST(shift)': 1}
- PCA2-T-095: {'ABST->ABST(same)': 3, 'NODEC->NODEC(same)': 1}
- PCA2-T-096: {'NODEC->NODEC(same)': 1}
- PCA2-T-098: {'ABST->NODEC(shift)': 1, 'POS->OTHER(loss)': 1}