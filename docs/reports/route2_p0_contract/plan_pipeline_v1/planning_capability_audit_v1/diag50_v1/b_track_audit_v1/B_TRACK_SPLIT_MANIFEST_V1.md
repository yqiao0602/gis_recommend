# 任务组级划分清单 V1（2026-10-18）

- **种子**：20261018；**范围**：29 reference records / 25 indivisible units (prototype for reference-set experiments; full-corpus split must reuse the same rules)
- **单元数**：25（train 18 / val 4 / test 3）
- **规则**：连通分量/独立组为不可拆分单元；测试集独立；全量语料划分必须复用同一规则。

| 单元 | 类型 | 组 | split |
| --- | --- | --- | --- |
| U6 | standalone | R02 | **train** |
| U20 | standalone | R17S105 | **train** |
| U13 | standalone | R11 | **train** |
| U22 | standalone | R22DIFF5 | **train** |
| U14 | standalone | R12 | **train** |
| U21 | standalone | R21 | **train** |
| U25 | standalone | R24AWEI | **train** |
| U19 | standalone | R17S068 | **train** |
| U1 | component | R03, R10 | **train** |
| U24 | standalone | R23 | **train** |
| U16 | standalone | R14 | **train** |
| U12 | standalone | R09 | **train** |
| U23 | standalone | R22S013 | **train** |
| U10 | standalone | R07 | **train** |
| U5 | standalone | R01 | **train** |
| U9 | standalone | R06 | **train** |
| U2 | component | R18A, R20 | **train** |
| U8 | standalone | R05 | **train** |
| U4 | component | R19, R22S027 | **val** |
| U18 | standalone | R16 | **val** |
| U17 | standalone | R15 | **val** |
| U15 | standalone | R13 | **val** |
| U3 | component | R18B, R24EUTRO | **test** |
| U11 | standalone | R08 | **test** |
| U7 | standalone | R04 | **test** |

## 说明

- 这是参考集原型划分；A/B/C 三组必须共用本清单（同一 split）。
- 全量训练语料构建后，以同一规则重新划分并替换本清单（新增版本号），不得静默覆盖。
