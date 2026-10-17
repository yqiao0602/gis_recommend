# Q2 归档冻结索引 V1（2026-10-18）

**用途**：冻结 Q2 判读证据链的版本关系与文件哈希，供数据治理与后续训练数据构建引用。

## 版本关系（commit）

- `d373203 2026-10-17 22:07:47 +0800 docs: weighted estimate report - owner spot-check round 1 amendment (3/3 maintained, same-bucket fidelity count aligned)`
- `e0f4df1 2026-10-17 22:06:58 +0800 B-track Q2: owner spot-check round 1 CLOSED - 3/3 primary labels maintained, cross-cutting rules registered`
- `eb58c83 2026-10-17 21:55:06 +0800 B-track Q2: all 117 adjudications COMPLETE + pool-level weighted estimate delivered`
- `981d94b 2026-10-17 21:20:36 +0800 B-track Q2 adjudication: batch 3 (S007/S008/S010/S011) registered - 8/117 + dual-category methodology ruling`
- `deb2dae 2026-10-17 21:15:25 +0800 B-track Q2 adjudication: S004 registered (4/117) - asset_version stratum now 4/4 overridden`
- `a759511 2026-10-17 21:10:26 +0800 B-track Q2 adjudication: owner batch 1 (S001-S003) registered - 3/117`
- `83ce634 2026-10-17 21:02:55 +0800 B-track Q2: owner pre-review archived + 117-dossier adjudication evidence pack (material gap filled)`
- `5430175 2026-10-17 20:44:41 +0800 B-track Q2: pool-level read-only re-scan EXECUTED per owner ruling + 117-record adjudication sample`

## 冻结文件（SHA-256）

| 文件 | 大小 | SHA-256（前 16） |
| --- | --- | --- |
| `Q2_OWNER_ADJUDICATION_V1.md` | 11772 | `8e21ee5c62a7c8e5` |
| `Q2_OWNER_ADJUDICATION_V1.json` | 24485 | `ff7d3514c95fb2bb` |
| `Q2_PRIORITY_VERIFICATION_PACKET_V1.md` | 47803 | `7b1ad27deb74f8b6` |
| `Q2_PRIORITY_VERIFICATION_PACKET_V1.json` | 92120 | `594c4f68b92b4ab7` |
| `Q2_PACKET_SCRIPT_PATHS_V1.json` | 2937 | `ddd0af9c65d39d15` |
| `Q2_V3_WALKTHROUGH_FINDINGS_V1.md` | 4815 | `653817f5cc1cecf6` |
| `Q2_V2P0_WALKTHROUGH_FINDINGS_V1.md` | 11267 | `c9118fba9ae324b7` |
| `Q2_SEMANTIC_AUDIT_CONCLUSION_V1.md` | 8116 | `bd4ce9c40f6d0438` |
| `Q2_POOL_RESCAN_MECHANICAL_V1.md` | 7377 | `de8483c2b7ec87d1` |
| `Q2_POOL_RESCAN_MECHANICAL_V1.json` | 6092 | `a1adebc2a941952b` |
| `Q2_POOL_RESCAN_ADJUDICATION_SAMPLE_V1.md` | 76866 | `75dc5a9cd0154ab6` |
| `Q2_POOL_RESCAN_ADJUDICATION_SAMPLE_V1.json` | 243078 | `da808bc21a71cf7b` |
| `Q2_POOL_RESCAN_RULING_OWNER_V1.md` | 8129 | `1421212973109f6e` |
| `Q2_POOL_WEIGHTED_ESTIMATE_V1.md` | 6296 | `8a44c062c886238d` |
| `Q2_ADMISSION_V1.json` | 108048 | `31c5974138a8d98e` |
| `Q2_EXTRACT_SAMPLE_V1.json` | 194059 | `250afdd06aac12f4` |
| `Q2_EXTRACT_RELATION_V1.json` | 112077 | `637e026578c2c34e` |
| `q2_rescan_adjudication_evidence_v1/LEDGER_V1.json` | 141859 | `0050831c8b95de1f` |
| `q2_rescan_adjudication_evidence_v1/INDEX.md` | 2424 | `59a748aa4449476e` |

## 归档规则

- 以上文件为 Q2 判读的权威证据；后续治理只新增文件与版本引用，**不覆盖**本索引内文件；
- 如需修订（如 17 条阻断深查），新增 `*_V1_1` 或记录进 `GOVERNANCE_CHANGE_LOG_V1.md` 并更新索引；
- 十对源码级证据（V3+V2P0）、117 条判读、池级加权估计、抽查裁定构成五层证据闭合。