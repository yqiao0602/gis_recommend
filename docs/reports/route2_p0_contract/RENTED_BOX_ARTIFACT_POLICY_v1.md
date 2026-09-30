# 租卡机产物回迁规则（OPERATIONAL RULE，2026-09-30 立）

**背景**：租用 GPU 服务器是**临时资源**（223.109.239.32:24924，租期 owner 掌握），
退租即一切清零。组内服务器 mdzhang（10.191.2.38，当前关机）才是持久资产的家。

**规则**：任何在租卡机上产生的**实验产物**，按以下优先级落盘（全部完成后该产物才算"安全"）：

1. **小件（报告/账本/日志/代码/adapter ≤50MB）→ 桌面机仓库**：
   `docs/reports/route2_p0_contract/<run_dir>/` 并 git commit（SHA 自证）。
2. **adapter/checkpoint 类（≤50MB）**：随 1 入库；更大的 checkpoint 存
   桌面 `Algorithm_classification\server_backup_<name>\` 并记 SHA 清单。
3. **mdzhang 恢复供电后**：将 1-2 的全部内容 rsync 到 mdzhang 对应路径
   （`/home/qy/system_redesign/...`）并双端 SHA 对账——此前桌面+U 盘为唯一持久副本。
4. **U 盘 bundle**：重要里程碑后重新生成 `route2_repo_bundle_*.bundle` 替换 U 盘旧版。
5. **不需要回迁的**：Base 模型权重（公开可重下，已留指纹）、venv（可重建）、
   数据已另有两份持久副本（02_DATA_FROZEN + mdzhang 备份）。

**适用范围**：Stage-1 训练/评测的全部产物、后续 Teacher Plan、B2 数据包、
任何在租卡机上跑出的实验结果。新 agent 接手时本规则随仓库文档生效。
