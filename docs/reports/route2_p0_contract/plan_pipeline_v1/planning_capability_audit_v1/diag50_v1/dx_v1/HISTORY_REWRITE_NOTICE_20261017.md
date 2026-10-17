# Git 历史重写通告（2026-10-17）

owner 裁定：4 个 >100MB 数据文件移出仓库（Algorithm_classification/repo_excluded_bigdata/，
SHA 见其 EXCLUDED_BIGDATA_MANIFEST.json）+ git-filter-repo 剥离全部历史。
**所有 2026-10-17 15:40 之前的提交哈希已改变。**

- 旧→新完整映射：repo_excluded_bigdata/commit-map-20261017.txt
- 关键Recent映射：d14f091e(dx_state V1)→38500bf；4d80fd49(docs sync)→597f95c
- 报告/记忆中引用的旧哈希仍可经映射表追溯；F 盘迁移包与 laptop 远端为旧历史，需重新同步
- 仓库体积：816MB → 337.5MB
