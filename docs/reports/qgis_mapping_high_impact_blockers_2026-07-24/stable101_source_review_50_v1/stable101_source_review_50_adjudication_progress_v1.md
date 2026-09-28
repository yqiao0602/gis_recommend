# stable101 50 条源码审核进度

全部 `review_index=1..50` 已审定，最终结论为 `accepted=19`、`deferred=3`、`rejected=28`、`pending=0`。`training_admission` 仍为 `not_granted_pending_deferred_resolution_and_export_gate`。

| # | 决定 | 关键依据 |
|---:|---|---|
| 1 | accepted | 限定无输入栅格分支后，rasterize -> fix -> zonal statistics -> zonal histogram 可证 |
| 2 | rejected | 五个独立工具函数被文件级扫描误拼为一条链 |
| 3 | deferred | 主流程存在，但 clip helper 每网格调用两次，当前链遗漏重复调用和 DAG 分支 |
| 4 | rejected | helper 定义顺序与实际嵌套调用顺序相反，且 difference 动态重复 |
| 5 | rejected | prepare_data 与 split_layer_constraints 的运行顺序被静态文件顺序倒置 |
| 6 | deferred | 两个可选 Processing 步骤和后续 SCR 自定义生成尚未表达 |
| 7 | rejected | 互斥 environmental/generic 分支被拼接，helper 顺序也被倒置 |
| 8 | accepted | 限定渲染表达式不对应现有字段的分支后，四步依赖完整 |
| 9 | rejected | 核心 USDA API 获取和内存图层构造未进入三步链 |
| 10 | rejected | 跨方法汇总遗漏 API、循环、统计和文件写出，且调用次数动态变化 |
| 11 | rejected | USDA API 与内存图层构造未进入五步链 |
| 12 | accepted | 同一 processAlgorithm 内 14 步顺序和连续字段依赖完整 |
| 13 | rejected | 三个互斥重分类分支被串联，可选分区统计被固定化 |
| 14 | rejected | 三个独立工具函数被文件级扫描误拼 |
| 15 | accepted | raster calculator -> polygonize -> buffer -> mask clip 直线依赖完整 |
| 16 | rejected | 黑边掩膜依赖 NumPy/GDAL 自定义生成，三步链遗漏核心任务 |
| 17 | accepted | RGB 编码 -> polygonize -> dissolve 串行依赖完整 |
| 18 | rejected | 条件裁剪、fallback warp、viewshed polygonize 和 hillshade 混为一链 |
| 19 | accepted | 完整入口证明 slope/hillshade 分支及 slope -> threshold -> polygonize 依赖 |
| 20 | accepted | NDVI -> threshold -> polygonize -> area ratio 串行依赖完整 |
| 21 | rejected | 两次低层 QgsRasterCalculator 未进入候选链 |
| 22 | accepted | 每个栅格按等间隔重分类后矢量化，两步依赖完整 |
| 23 | rejected | 抽象基类的栅格、矢量和子类 helper 被合并 |
| 24 | rejected | 点/面分支与栅格分支互斥，五步无法同时执行 |
| 25 | accepted | 河流缓冲、与水体合并、范围裁剪、栅格化和重投影完整 |
| 26 | accepted | 空间提取 -> 栅格化 -> 掩膜裁剪直线依赖完整 |
| 27 | accepted | 每个矢量图层 rasterize -> translate PNG 两步完整 |
| 28 | rejected | 条件模式混合，且 DSM-DEM 低层数组计算未入链 |
| 29 | rejected | rasterize 与 warp 属于互斥基准面分支 |
| 30 | rejected | 显式 grass7:r.watershed 被候选链遗漏 |
| 31 | accepted | 入口函数证明跨 helper 的 fix -> clip 调用顺序和数据依赖 |
| 32 | accepted | 修复后的分区图层直接进入人口栅格 zonal statistics |
| 33 | rejected | 经线切割线由低层 API 构造，当前三步链遗漏核心几何生成 |
| 34 | rejected | 四个独立工具函数被误拼，动态 GDAL 调用也被遗漏 |
| 35 | accepted | 面板布置线 fix -> dissolve -> polygonize 连续依赖完整 |
| 36 | rejected | 完整模型的 GRASS 水文和矢量化前置步骤被候选链删除 |
| 37 | rejected | 跨函数误拼，且两条已注释 Processing 调用被计入候选 |
| 38 | rejected | 五次 fix 分属四个独立命令入口，不是串行链 |
| 39 | accepted | 每个分析图层 extract-by-location -> fix -> intersection 完整 |
| 40 | rejected | 四个独立 helper 与循环方法被拼成固定十二步链 |
| 41 | rejected | notebook 中三个独立代码示例被文件级顺序误拼 |
| 42 | deferred | 三次条件重投影和两次求交被压缩为一次加一次，调用图可恢复 |
| 43 | accepted | 限定两个输出均存在时，crossings 和 kerbs 分别重投影 |
| 44 | accepted | 栅格和点并行重投影后汇合到 raster sampling |
| 45 | rejected | 两个独立工具函数没有文件内调用入口 |
| 46 | accepted | 筛选、求交、融合、保留字段、重投影、算面积和保存连续完整 |
| 47 | rejected | 矢量与栅格重投影属于两个独立公共函数 |
| 48 | rejected | protected join 与 multiintersection 属于不同函数，且后者依赖低层合并 |
| 49 | rejected | 中间核心属性转换未入链，retainfields 还是可选分支 |
| 50 | accepted | 限定 CRS 不一致分支后，边界重投影 -> 掩膜裁剪完整 |

这里的 `rejected` 表示“当前抽取出的候选链不能训练”，不表示整个源码文件无价值。被拒源码中的局部函数或分支仍可在调用图展开、注释过滤、混合 API 表达和工作流切分后重新入池。

本轮审核确认：`source_snippet_contains_all_ops=true` 只能证明源码里出现了这些调用，不能证明它们属于同一条可执行工作流。跨 helper 只有在入口函数证明真实调用顺序和数据流时才可准入；并行分支可在输入条件明确、调用次数完整且汇合关系可证时准入。下一门禁是单独处理 #3、#6、#42 三条 deferred，并对 19 条 accepted 做确定性训练导出验证。
