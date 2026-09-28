# Gate 2 判定规则（2026-09-15 冻结，基于 Batch1 校准）

## 核心判据
> 只看最终用于模型输入的 Task Text：如果仅凭 Task Text，模型已经知道
> "应该执行哪个具体操作或操作序列"，则判 C/D；
> 如果只是知道目标、对象、领域或结果，还需模型完成 Task→Operator 推理，则最高判 B。

## 标签定义
- A — Clean: 只描述用户目标
- B — Mild: 有领域术语/结果/参数描述，但不泄露算子；模型仍需自行推理 Task→Operator
- C — Workflow leakage: 明确告知操作/顺序（"切段→连接→计数"），但无 API/算子 ID
- D — Hard leakage: 泄漏与答案相关的 API/算子 ID/实现（如 gdal:rasterize、GRASS v.to.3d、GDAL Translate）

## 已定边界判例
1. 泛技术栈提及（GDAL/rasterio/NumPy/matplotlib 库名）≠ D（#10 判例）——D 要求泄漏内容与答案算子的身份或实现直接相关
2. 脚本私有函数名（get_lista_codigos）≠ 单独构成 D，属实现细节，按 C 处理（#4 判例）
3. 公式/参数细节（AWEIsh 公式）不泄漏算子 → B，但标记"参数层泄漏"（#7 判例）
4. 功能性描述答案（"reprojecting the bounding box"）若未组织成执行步骤 → B（#9 判例）
5. 【Q2 裁定】按"实际用于训练的任务文本"判：NAME 干净 + DESC 泄漏 → 资产保留，
   可走 SFT_TaskText=NAME 路线（#5/#8 判例）。审计需分别记录 label(NAME) 与 label(DESC)。

## Batch1 裁定（10条）
1:D 2:C 3:D 4:C 5:D 6:B 7:B 8:D 9:B 10:B
其中 #5/#8: label(DESC)=D, label(NAME)=A（可挽救）

## Batch2 追加规则（2026-09-15）
- Q3: D 不限于内部 ID 字符串——任何唯一指向目标算子的名称形态都算 D
  （native:pointstopath / 'Points to Path' 显示名 / QgsGeometry.xxx / processing.run(...)）
- Q4: operator_quality 轴正式加入，与 Gate 2 正交：
  valid(真实GIS处理算子) / weak(边缘) / degenerate(框架对象/图层加载/服务配置等非处理目标)
- 治理框架升级：从"删除 workflow"改为"筛选可用的 Task Text × Workflow 配对"
  （NAME 与 DESC 是两个独立的 Task Text 候选版本）

## Batch2 裁定（10条）
11:D 12:C 13:C 14:C 15:C 16:C 17:C 18:D 19:D 20:B
其中 #11/#19: label(DESC)=D, label(NAME)=A（可挽救）
#20: task=B, operator_quality=degenerate（QgsProcessingContext.LayerDetails 非真实算子）

## Batch3 追加规则（2026-09-15）
- Q5: "目标语义与算子语义重合" != "任务文本泄漏答案"——单算子任务天然与算子名相似
  (Compute slope from DEM / Set Z coordinate from DEM / Translate raster layer 均为合法用户目标)
  判泄漏的唯准绳: 任务文本是否提供了实现路径使模型无需自行选择算子
- #25 判例: 任务知识(公式/指数)属B; 但下游步骤叙述(polygonized/filtered)进入答案序列则整体升C
- 二维框架定型: Task Independence (A/B/C/D) x Operator Quality (valid/weak/degenerate)

## Batch3 裁定
21:D 22:D 23:B 24:C 25:C 26:B 27:B 28:C 29:D 30:B

## Batch4 追加规则（2026-09-15）
- #36 判例: NAME 描述"最终目标/处理结果"(Rasterize and fill X) -> B; 只有给出完整实现路径
  ("先裁剪再栅格化再填补最后掩膜")才 C。与#27同类: 目标语义与算子语义重合!=泄漏
- #35 判例: Task里出现PDAL等真实实现技术但答案算子未包含之 -> 不构成D(泄漏须指向答案)
- 战略结论(初步,待95条全量验证): DESC 不适合作为核心SFT Task Text(C+D=72.5%于40条);
  NAME 为主要候选。审计框架: NAME与DESC并行做Gate 2标注,不预先判死刑

## Batch4 裁定
31:C 32:C 33:D 34:C 35:B 36:C 37:B 38:C 39:C 40:C  (#36 NAME=B)
