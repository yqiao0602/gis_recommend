# GEE Extractor v2 P0-B Native JavaScript Classification Design

日期：2026-07-23

## 目标

消除 Extractor v2 将标准 JavaScript 全局命名空间调用误记为 GEE core 的确定性假阳性，同时保留未知 receiver 的保守语义。P0-B 只改调用分类和质量标记，不处理 UI/native 类型推断、helper 绑定、控制流、taxonomy 或训练准入。

## 已确认问题

当前 `_classify()` 对所有包含点号但不属于已知 `ee`、`Export`、`Map`、`ui`、`Chart` 前缀的调用返回 `core/receiver_untyped`。因此 `Math.pow`、`Object.keys`、`Date.getFullYear`、`JSON.parse` 等标准库调用会进入 core operator chain。另一方面，`image.select`、`collection.map`、`decisionTree.join`、`panel.getValue` 等变量 receiver 的静态类型通常无法由局部 AST 证明，不能一概降级。

## 方案选择

1. 将所有非 `ee.*` dotted call 降级：会漏掉真实 GEE 变量 receiver，否决。
2. 根据变量名或方法名猜测 UI/native 类型：会把领域对象误判，且无法审计，否决。
3. 只对标准 JavaScript 全局 namespace 做确定性 allowlist 分类，其余保持原有 `receiver_untyped`：改动小、可验证、符合 fail-closed，采用。

## 分类合同

- 新增 `_NATIVE_JS_NAMESPACES` allowlist，覆盖本阶段已观察到的 `Math`、`Object`、`Date`、`Array`、`String`、`Number`、`Boolean`、`RegExp`、`JSON`、`console`、`Promise`、`Reflect`、`Proxy`、`Symbol`、`BigInt`、`Intl`、`Set`、`WeakSet`、`WeakMap`、`ArrayBuffer`、`DataView`、`Error` 等标准全局根。
- `raw_callee` 以 `root.method` 形式且 root 在 allowlist 时，分类为 `support`，resolution=`native_js_namespace`，并添加 `native_js_call` flag。它进入 `support_calls`，不会进入 `core_operator_chain`。
- 标准 namespace 的调用顺序、源码位置和参数 receiver 遍历保持不变；只改变分类层。
- `ee.*`、`Export.*`、`Map.*`、`ui.*`、`Chart.*` 的现有优先级和分类保持不变。
- 任意本地变量 receiver、动态计算属性和未在 allowlist 中的 namespace 继续返回 `core/receiver_untyped`，保留 `untyped_receiver` flag，不删除 evidence。

## 明确不做

- 不把 `panel`、`widgets`、`batch`、`AppCreator`、`decisionTree`、`image` 等变量名加入 allowlist；
- 不将未知 receiver 统一标记为 unresolved；
- 不改变 `FunctionDeclaration`、变量函数、对象属性函数或 callback 展开；
- 不处理循环 cardinality、运行时全序、QGIS/GEE 映射或训练数据。

## 测试与验收

回归测试覆盖标准 namespace 的 support 分类、`native_js_call` quality flag、标准调用链的顺序保留、未知变量 receiver 继续为 core/receiver_untyped，以及现有 GEE/UI/Export 分类不回退。完成后运行 Extractor v2、replay、P0/legacy/provenance 门禁、compileall 和 diff 检查。P0-B 结果只作为诊断，不授予人工 gold 或训练准入。
